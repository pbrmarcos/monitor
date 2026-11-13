import hashlib
import json
import time

import httpx
from fastapi.testclient import TestClient

from monitor.main import create_app
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}
FILES = {'config.json': b'{"alignment_heads": []}', 'tokenizer.json': b'{"version": "1.0"}', 'vocabulary.txt': b'a\nb\n',
         'model.bin': bytes(range(256)) * 400}


class FakeEngine:
    def __init__(self, path):
        self.path, self.calls = path, []

    def transcribe(self, audio, prompt=''):
        self.calls.append((audio, prompt))
        return 'Olá, preciso de um orçamento para a Nextlink.'


class Hub:
    """Repositório de modelos simulado: lista de arquivos com tamanhos, SHA-256 e suporte a Range."""

    def __init__(self, corrupt=False):
        self.requests, self.corrupt = [], corrupt

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.startswith('/api/models/'):
            digest = hashlib.sha256(FILES['model.bin']).hexdigest()
            siblings = [{'rfilename': name, 'size': len(data), **({'lfs': {'sha256': digest}} if name == 'model.bin' else {})}
                        for name, data in FILES.items()] + [{'rfilename': 'README.md', 'size': 10}]
            return httpx.Response(200, json={'siblings': siblings})
        name = request.url.path.rsplit('/', 1)[-1]
        data = FILES[name]
        if self.corrupt and name == 'model.bin':
            data = b'\x00' * len(data)
        if 'range' in request.headers:
            start = int(request.headers['range'].split('=')[1].split('-')[0])
            return httpx.Response(206, content=data[start:])
        return httpx.Response(200, content=data)


def make(tmp_path, hub=None, **kwargs):
    kwargs.setdefault('voice_installed', True)
    app = create_app(tmp_path, 'session', False, secret_store=MemoryStore(), voice_engine=FakeEngine,
                     voice_transport=httpx.MockTransport(hub) if hub else None, **kwargs)
    return app, TestClient(app, headers=HEADERS)


def wait_download(api):
    for _ in range(200):
        status = api.get('/voice').json()
        if not status['downloading']:
            return status
        time.sleep(0.02)
    raise AssertionError('download não terminou')


def test_model_is_downloaded_verified_and_then_used_to_transcribe(tmp_path):
    hub = Hub()
    app, client = make(tmp_path, hub)
    with client as api:
        start = api.get('/voice').json()
        assert start['engine'] and not start['ready'] and start['size'] == 'small'
        assert [item['id'] for item in start['sizes']] == ['tiny', 'base', 'small']
        blocked = api.post('/assistant/transcribe', content=b'audio', headers={'Content-Type': 'audio/webm'})
        assert blocked.status_code == 409 and 'Baixe o modelo de voz' in blocked.json()['detail']

        assert api.put('/voice', json={'size': 'tiny'}).json()['size'] == 'tiny'
        assert api.put('/voice', json={'size': 'enorme'}).status_code == 400
        assert api.post('/voice/download').status_code == 202
        done = wait_download(api)
        assert done['ready'] and done['error'] == '' and done['progress'] == 1.0
        asked = {request.url.path.rsplit('/', 1)[-1] for request in hub.requests if 'resolve' in request.url.path}
        assert asked == {'config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt'}  # README e outros não são baixados
        assert all('Systran/faster-whisper-tiny' in str(request.url) for request in hub.requests)

        api.put('/preferences', json={**api.get('/preferences').json(), 'fronts': ['Rocha', 'Nextlink', 'Carteira', 'WebQ']})
        audio = b'RIFFfake-audio'
        result = api.post('/assistant/transcribe', content=audio, headers={'Content-Type': 'audio/webm'})
        assert result.json() == {'text': 'Olá, preciso de um orçamento para a Nextlink.'}
        sent, prompt = app.state.voice.engine.calls[0]
        assert sent == audio and 'Nextlink' in prompt and 'Monitor' in prompt  # nomes das frentes ajudam no reconhecimento

        assert api.post('/voice/download').status_code == 202  # já baixado: confere e termina sem baixar de novo
        before = len(hub.requests)
        assert wait_download(api)['ready'] and len([r for r in hub.requests[before:] if 'resolve' in r.url.path]) == 0
        assert api.delete('/voice').status_code == 204 and not api.get('/voice').json()['ready']


def test_corrupted_download_is_rejected(tmp_path):
    app, client = make(tmp_path, Hub(corrupt=True))
    with client as api:
        api.put('/voice', json={'size': 'tiny'})
        api.post('/voice/download')
        status = wait_download(api)
        assert not status['ready'] and 'não confere' in status['error']
        assert not (app.state.voice.path('tiny') / 'model.bin').exists()
        assert api.post('/assistant/transcribe', content=b'x', headers={'Content-Type': 'audio/webm'}).status_code == 409


def test_interrupted_download_resumes_with_range(tmp_path):
    hub = Hub()
    app, client = make(tmp_path, hub)
    with client as api:
        api.put('/voice', json={'size': 'tiny'})
        directory = app.state.voice.path('tiny')
        directory.mkdir(parents=True)
        (directory / 'model.bin.part').write_bytes(FILES['model.bin'][:5000])
        api.post('/voice/download')
        assert wait_download(api)['ready']
        ranged = [r for r in hub.requests if r.url.path.endswith('model.bin') and 'range' in r.headers]
        assert ranged and ranged[0].headers['range'] == 'bytes=5000-'
        assert (directory / 'model.bin').read_bytes() == FILES['model.bin']


def test_offline_network_reports_a_clear_error_and_engine_missing_blocks_everything(tmp_path):
    def offline(request):
        raise httpx.ConnectError('offline', request=request)

    app, client = make(tmp_path, offline)
    with client as api:
        api.post('/voice/download')
        assert 'Verifique a conexão' in wait_download(api)['error']
    app, client = make(tmp_path / 'sem-motor', Hub(), voice_installed=False)
    with client as api:
        assert api.get('/voice').json()['engine'] is False
        assert api.post('/voice/download').status_code == 503
        assert api.post('/assistant/transcribe', content=b'x', headers={'Content-Type': 'audio/webm'}).status_code == 503


def test_audio_limits_failures_and_idle_unload(tmp_path):
    app, client = make(tmp_path, Hub())
    with client as api:
        api.put('/voice', json={'size': 'tiny'})
        api.post('/voice/download')
        wait_download(api)
        assert api.post('/assistant/transcribe', content=b'', headers={'Content-Type': 'audio/webm'}).status_code == 400
        too_big = api.post('/assistant/transcribe', content=b'a' * (12 * 1024 * 1024 + 1), headers={'Content-Type': 'audio/webm'})
        assert too_big.status_code == 413
        api.post('/assistant/transcribe', content=b'ok', headers={'Content-Type': 'audio/webm'})
        voice = app.state.voice
        assert voice.engine is not None
        voice.unload_idle()
        assert voice.engine is not None  # recém-usado
        voice.last_used -= 3600
        voice.unload_idle()
        assert voice.engine is None

        class Broken:
            def transcribe(self, audio, prompt=''):
                raise RuntimeError('detalhe interno C:\\segredo')

        voice.engine, voice.engine_size = Broken(), 'tiny'
        failed = api.post('/assistant/transcribe', content=b'ruido', headers={'Content-Type': 'audio/webm'})
        assert failed.status_code == 422 and 'segredo' not in json.dumps(failed.json())
