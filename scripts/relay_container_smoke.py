"""Verifica imagem Docker real; usa apenas credenciais públicas de teste no CI."""
import argparse
import json
import os
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['send', 'ack'])
args = parser.parse_args()
base = 'http://127.0.0.1:8090'
for _ in range(30):
    try:
        with urlopen(base + '/health', timeout=2) as response:
            assert json.load(response)['ok']
        break
    except URLError:
        time.sleep(1)
else:
    raise RuntimeError('Relay did not start')


def call(path, token, body=None, extra=None):
    request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', **(extra or {})})
    with urlopen(request, timeout=5) as response:
        payload = response.read()
        return json.loads(payload) if payload else None


app_token = os.environ['RELAY_APP_TOKEN']
site_token = json.loads(os.environ['RELAY_SITE_TOKENS'])['1']
payload = dict(submission_id='container-test-001', email='synthetic@example.org', message='Container smoke test')
if args.phase == 'send':
    call('/forms/1', site_token, payload, {'X-Monitor-Test': '1'})
    assert call('/events', app_token) == []
    first = call('/forms/1', site_token, payload)
    assert call('/forms/1', site_token, payload) == first
    assert len(call('/events', app_token)) == 1
else:
    events = call('/events', app_token)
    assert len(events) == 1, 'Queued contact must survive container restart'
    call('/events/ack', app_token, {'ids': [events[0]['id']]})
    assert call('/events', app_token) == []
print(f'Relay container {args.phase}: OK')
