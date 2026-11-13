import base64
import json

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor import assistant_skills
from monitor.assistant_records import metrics, start
from monitor.main import create_app
from monitor.models import AssistantRun, ChatMetrics

HEADERS = {'Authorization': 'Bearer session'}
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def make(path):
    return TestClient(create_app(path, 'session', False), headers=HEADERS)


def fake_model(monkeypatch, *, fail=False):
    real, seen = httpx.Client, []

    def handler(request):
        assert 'Authorization' not in request.headers
        seen.append(json.loads(request.content))
        if fail:
            raise httpx.ConnectError('offline', request=request)
        final = dict(done=True, eval_count=48, eval_duration=2_000_000_000, prompt_eval_count=100,
                     prompt_eval_duration=500_000_000, load_duration=10_000_000, total_duration=2_510_000_000)
        return httpx.Response(200, text=json.dumps({'message': {'content': 'Resposta de teste'}}) + '\n' + json.dumps(final))

    monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return seen


def test_image_preview_requires_auth_works_after_send_and_disappears_with_conversation(tmp_path, monkeypatch):
    fake_model(monkeypatch)
    with make(tmp_path) as api:
        conversation = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        image = api.post('/assistant/attachments', json={'name': 'private.png', 'data': base64.b64encode(PNG).decode()}).json()
        path = f'/assistant/attachments/{image["id"]}/preview'
        assert api.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401
        api.post(f'/assistant/conversations/{conversation}/messages', json={'content': 'Leia esta imagem', 'attachments': [image['id']]})
        response = api.get(path)
        assert response.headers['cache-control'] == 'no-store'
        assert response.json()['src'] == 'data:image/png;base64,' + base64.b64encode(PNG).decode()
        api.delete(f'/assistant/conversations/{conversation}')
        assert api.get(path).status_code == 404


def test_metrics_are_real_persist_and_survive_clearing_private_logs(tmp_path, monkeypatch):
    seen = fake_model(monkeypatch)
    with make(tmp_path) as api:
        conversation = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        response = api.post(f'/assistant/conversations/{conversation}/messages', json={'content': 'Resposta para cliente: SEGREDO-DO-CLIENTE'})
        events = [json.loads(line) for line in response.text.splitlines()]
        assert events[-1]['metrics']['tokens_per_second'] == 24
        assert events[-1]['metrics']['output_tokens'] == 48
        assert seen[0]['options']['num_ctx'] == 16384
        logs = api.get('/assistant/records').json()
        assert logs[0]['status'] == 'completed' and logs[0]['skills']
        assert 'SEGREDO-DO-CLIENTE' not in json.dumps(logs)
        assert 'Resposta de teste' not in json.dumps(logs)
        assert api.get(f'/assistant/conversations/{conversation}/messages').json()[-1]['metrics']['tokens_per_second'] == 24
        api.delete('/assistant/records')
        assert api.get('/assistant/records').json() == []
        assert api.get(f'/assistant/conversations/{conversation}/messages').json()[-1]['metrics']['tokens_per_second'] == 24
        api.delete(f'/assistant/conversations/{conversation}')
        with Session(api.app.state.engine) as db:
            assert db.exec(select(ChatMetrics)).all() == []


def test_metrics_never_fabricate_speed_for_missing_or_zero_duration():
    assert metrics({}) == {}
    assert 'tokens_per_second' not in metrics({'eval_count': 20, 'eval_duration': 0})
    assert metrics({'eval_count': 20, 'eval_duration': 500_000_000})['tokens_per_second'] == 40
    assert metrics({'eval_count': True, 'eval_duration': float('nan')}) == {}


def test_skills_are_selective_bounded_and_can_be_disabled_or_added(tmp_path):
    with make(tmp_path) as api:
        original_model = api.get('/settings').json()['model']
        assert len(api.get('/assistant/skills').json()) == 4
        custom = api.post('/assistant/skills', json={'name': 'Revisão cuidadosa', 'keywords': 'contrato', 'instructions': 'Confira datas e destaque ambiguidades antes de sugerir qualquer compromisso.'}).json()
        with Session(api.app.state.engine) as db:
            chosen = assistant_skills.choose(db, 'Leia o contrato da proposta do cliente', image=True)
            assert len(chosen) == 2 and chosen[0]['id'] == 'vision'
            assert assistant_skills.choose(db, 'Fale de astronomia') == []
        api.put('/assistant/skills/vision', json={'enabled': False})
        with Session(api.app.state.engine) as db:
            assert assistant_skills.choose(db, 'imagem', image=True) == []
            assert any(item['id'] == custom['id'] for item in assistant_skills.choose(db, 'Revise este contrato'))
        assert api.get('/settings').json()['model'] == original_model
        assert api.post('/assistant/skills', json={'name': 'Test', 'keywords': 'test', 'instructions': 'x' * 601}).status_code == 422
        assert api.delete('/assistant/skills/vision').status_code == 400
        assert api.delete('/assistant/skills/' + custom['id']).status_code == 204


def test_failed_and_interrupted_runs_are_visible_and_retention_is_bounded(tmp_path, monkeypatch):
    fake_model(monkeypatch, fail=True)
    with make(tmp_path) as api:
        conversation = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        api.post(f'/assistant/conversations/{conversation}/messages', json={'content': 'Olá'})
        assert api.get('/assistant/records').json()[0]['status'] == 'error'
        with Session(api.app.state.engine) as db:
            for index in range(205):
                db.add(AssistantRun(status='completed', detail=str(index)))
            db.commit()
        interrupted = start(api.app.state.engine, conversation)
        assert len(api.get('/assistant/records').json()) == 200
    with make(tmp_path) as restarted:
        row = next(row for row in restarted.get('/assistant/records').json() if row['id'] == interrupted)
        assert row['status'] == 'interrupted'


def test_local_actions_are_logged_without_model_speed(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('A ferramenta local não precisa consultar a LLM')
    monkeypatch.setattr('monitor.assistant.stream', forbidden)
    with make(tmp_path) as api:
        conversation = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        response = api.post(f'/assistant/conversations/{conversation}/messages', json={'content': 'Crie um lembrete Consulta privada amanhã às 9h'})
        assert '"action"' in response.text
        row = api.get('/assistant/records').json()[0]
        assert row['kind'] == 'action' and row['status'] == 'completed'
        assert row['detail'] == 'Lembrete criado' and row['metrics'] == {}
        assert 'Consulta privada' not in json.dumps(row)


def test_diagnostics_reads_only_model_memory_and_never_changes_configuration(tmp_path, monkeypatch):
    real = httpx.Client
    def handler(request):
        assert request.method == 'GET' and request.url.path == '/api/ps'
        assert 'Authorization' not in request.headers
        return httpx.Response(200, json={'models': [{'name': 'qwen3.5:4b-q4_K_M', 'size_vram': 3555731700,
                                                  'size': 3555731700, 'context_length': 16384, 'digest': 'not-exposed'}]})
    monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with make(tmp_path) as api:
        before = api.get('/settings').json()
        data = api.get('/assistant/diagnostics').json()
        assert data['context'] == 16384 and data['skills_per_request'] == 2
        assert data['loaded'][0]['size_vram'] == 3555731700 and 'digest' not in data['loaded'][0]
        assert api.get('/settings').json() == before
