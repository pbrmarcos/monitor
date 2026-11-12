"""Verify production scheduling and timezone data in the packaged Windows backend."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.error import URLError

root = Path(__file__).resolve().parents[1]
temporary = root / 'tmp'
temporary.mkdir(exist_ok=True)
binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'app/desktop/src-tauri/binaries/monitor-backend.exe'

with tempfile.TemporaryDirectory(prefix='agenda-sidecar-', dir=temporary) as directory:
    assert Path(directory).resolve().is_relative_to(temporary.resolve())
    child = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env={**os.environ, 'LOCALAPPDATA': directory, 'MONITOR_DEMO': '0', 'MONITOR_PARENT_PIPE': '1'})
    try:
        handshake = json.loads(child.stdout.readline())
        base = f"http://127.0.0.1:{handshake['port']}"

        def call(path, body=None):
            request = urllib.request.Request(base + path, headers={'Authorization': f"Bearer {handshake['token']}",
                                             'Content-Type': 'application/json'},
                                             data=json.dumps(body).encode() if body is not None else None)
            if path == '/storage':
                request.method = 'PUT'
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)

        for _ in range(50):
            try:
                call('/health')
                break
            except URLError:
                time.sleep(.1)
        else:
            raise RuntimeError('Packaged API did not start')
        # Avoid using any real folder selected in a previous installed version.
        call('/storage', {'files_dir': str(Path(directory) / 'Files')})
        item = call('/reminders', {'text': 'Synthetic packaged scheduler test',
                                  'when': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if any(n['kind'] == 'lembrete' and n['reminder_id'] == item['id'] for n in call('/notifications')):
                break
            time.sleep(.25)
        else:
            raise AssertionError('Packaged scheduler did not generate the reminder')
        assert call('/reminders')[0]['status'] == 'disparado'
        print('Packaged reminder scheduler: UTC, timezone data, durable event and real worker OK')
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'], capture_output=True, check=False)
            child.wait(timeout=5)
            raise
        finally:
            child.stdout.close()
            child.stderr.close()
