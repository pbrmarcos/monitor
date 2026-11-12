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
    env = {**os.environ, 'LOCALAPPDATA': folder, 'MONITOR_DEMO': '0'}
    child = subprocess.Popen([str(root / 'app/desktop/src-tauri/binaries/monitor-backend.exe')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
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
        print('Packaged backend: handshake, auth, create and local database OK')
    finally:
        child.terminate()
        child.communicate(timeout=15)
