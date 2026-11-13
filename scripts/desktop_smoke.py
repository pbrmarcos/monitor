"""Validate packaged sidecar handshake, authentication and persistent CRUD."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
from urllib.error import HTTPError, URLError

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    env = {**os.environ, 'LOCALAPPDATA': folder, 'MONITOR_DEMO': '0', 'MONITOR_PARENT_PIPE': '1'}
    child = subprocess.Popen([str(root / 'app/desktop/src-tauri/binaries/monitor-backend.exe')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        handshake = json.loads(child.stdout.readline())
        url = f"http://127.0.0.1:{handshake['port']}"
        headers = {'Authorization': f"Bearer {handshake['token']}", 'Content-Type': 'application/json'}
        for _ in range(50):
            try:
                urllib.request.urlopen(urllib.request.Request(url+'/health',headers=headers), timeout=2)
                break
            except (URLError, HTTPError):
                time.sleep(.2)
        else:
            raise RuntimeError('Sidecar did not become ready')
        try:
            urllib.request.urlopen(url+'/demands')
            raise AssertionError('Unauthenticated request was accepted')
        except HTTPError as error:
            assert error.code == 401
        request = urllib.request.Request(url+'/demands', headers=headers, data=json.dumps({'title':'Teste do executável','front_id':1}).encode(), method='POST')
        with urllib.request.urlopen(request) as response:
            demand = json.load(response)
            assert demand['id'] == 1
        assert (Path(folder)/'Monitor/monitor.db').exists()
        def assistant_call(path, method='GET', payload=None):
            body = json.dumps(payload).encode() if payload is not None else None
            with urllib.request.urlopen(urllib.request.Request(url + path, headers=headers, data=body, method=method), timeout=5) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        conversation = assistant_call('/assistant/conversations', 'POST', {'mode': 'general'})
        assert assistant_call(f"/assistant/conversations/{conversation['id']}/messages") == []
        payload = {'content': 'Crie um lembrete Consulta de exemplo 08/12/2099 as 14:30'}
        request = urllib.request.Request(url + f"/assistant/conversations/{conversation['id']}/messages", headers=headers,
                                         data=json.dumps(payload).encode(), method='POST')
        with urllib.request.urlopen(request, timeout=10) as response:
            action_events = [json.loads(line) for line in response.read().decode().splitlines()]
        assert any(item.get('action', {}).get('kind') == 'reminder' for item in action_events)
        saved_reminders = assistant_call('/reminders')
        assert saved_reminders[0]['text'] == 'Consulta de exemplo'
        rule = assistant_call('/assistant/rules', 'POST', {'text': 'Responder sempre com clareza'})
        assert any(item['id'] == rule['id'] for item in assistant_call('/assistant/rules'))
        assistant_call(f"/assistant/conversations/{conversation['id']}", 'DELETE')
        assistant_call(f"/assistant/rules/{rule['id']}", 'DELETE')
        print('Packaged backend: handshake, auth, demands, conversations, preferences and local database OK')
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'], check=False, capture_output=True)
            child.wait(timeout=5)
            raise
        finally:
            child.stdout.close()
            child.stderr.close()
