import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

BACKEND = Path(__file__).resolve().parents[1]


def test_native_voice_libraries_load_while_the_parent_watcher_is_running_and_backend_exits_with_parent(tmp_path):
    """O aplicativo desktop inicia o backend com um pipe no stdin. Uma leitura bloqueada nesse pipe travava o carregamento
    das bibliotecas nativas do Whisper; o backend também precisa encerrar quando o aplicativo fecha o pipe."""
    fake = tmp_path / 'Monitor' / 'voice' / 'tiny'
    fake.mkdir(parents=True)
    for name in ('config.json', 'model.bin', 'tokenizer.json', '.verified'):
        (fake / name).write_bytes(b'x')
    child = subprocess.Popen([sys.executable, '-u', str(BACKEND / 'run_backend.py')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True,
                             env={**os.environ, 'LOCALAPPDATA': str(tmp_path), 'MONITOR_DEMO': '0', 'MONITOR_PARENT_PIPE': '1'})
    try:
        handshake = json.loads(child.stdout.readline())
        base = f"http://127.0.0.1:{handshake['port']}"

        def call(path, data=None, method=None, content_type='application/json'):
            request = urllib.request.Request(base + path, data=data, method=method,
                                             headers={'Authorization': f"Bearer {handshake['token']}", 'Content-Type': content_type})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return response.status
            except HTTPError as error:
                return error.code

        for _ in range(100):
            try:
                if call('/health') == 200:
                    break
            except OSError:
                time.sleep(0.1)
        assert call('/voice', b'{"size":"tiny"}', 'PUT') == 200
        # Modelo falso: o motor carrega e recusa o modelo (422). Travar aqui é a regressão.
        assert call('/assistant/transcribe', b'audio', None, 'audio/webm') == 422
        child.stdin.close()
        assert child.wait(timeout=20) is not None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
