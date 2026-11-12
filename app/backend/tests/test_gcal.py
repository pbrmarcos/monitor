import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from monitor import gcal
from monitor.main import create_app
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}
CLIENT = {'client_id': 'cliente-123.apps.googleusercontent.com', 'client_secret': 'segredo-do-cliente'}


class FakeGoogle:
    def __init__(self):
        self.events, self.requests, self.revoked = {}, [], False

    def __call__(self, request):
        self.requests.append(request)
        path = request.url.path
        if request.url.host == 'oauth2.googleapis.com':
            form = parse_qs(request.content.decode())
            if self.revoked:
                return httpx.Response(400, json={'error': 'invalid_grant'})
            assert form['client_id'] == [CLIENT['client_id']] and form['client_secret'] == [CLIENT['client_secret']]
            if form['grant_type'] == ['authorization_code']:
                assert form['code'] == ['codigo'] and len(form['code_verifier'][0]) > 42
                return httpx.Response(200, json={'access_token': 'acesso', 'refresh_token': 'renovacao', 'expires_in': 3600,
                                                 'scope': 'https://www.googleapis.com/auth/calendar.events email'})
            assert form['refresh_token'] == ['renovacao']
            return httpx.Response(200, json={'access_token': 'acesso', 'expires_in': 3600})
        assert request.headers['Authorization'] == 'Bearer acesso'
        if path.endswith('/userinfo'):
            return httpx.Response(200, json={'email': 'pessoa@example.com'})
        identifier = path.rsplit('/', 1)[-1]
        if request.method == 'POST':
            body = json.loads(request.content)
            if body['id'] in self.events:
                return httpx.Response(409, json={})
            self.events[body['id']] = body
            return httpx.Response(200, json=body)
        if identifier not in self.events:
            return httpx.Response(404, json={})
        if request.method == 'PUT':
            self.events[identifier] = json.loads(request.content)
            return httpx.Response(200, json={})
        del self.events[identifier]
        return httpx.Response(204)

    def writes(self):
        return len([r for r in self.requests if 'calendar/v3' in r.url.path])


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(gcal, 'TRANSPORT', httpx.MockTransport(fake))
    gcal._access.clear()
    yield fake
    gcal._access.clear()


def settle(api):
    """Espera o envio em segundo plano e roda até não haver mais nada a mudar."""
    for _ in range(200):
        if gcal._lock.acquire(blocking=False):
            gcal._lock.release()
            result = api.post('/calendar/sync').json()
            if result['created'] + result['updated'] + result['removed'] == 0:
                return
        time.sleep(0.02)
    raise AssertionError('a sincronização não terminou')


def connect(api):
    opened = []
    api.app.state.open_browser = opened.append
    assert api.post('/calendar/connect').status_code == 400  # sem cliente OAuth
    saved = api.put('/calendar/client', json=CLIENT).json()
    assert saved['configured'] and not saved['connected'] and 'segredo' not in json.dumps(saved)
    assert api.post('/calendar/connect').status_code == 200
    query = parse_qs(urlparse(opened[0]).query)
    assert query['code_challenge_method'] == ['S256'] and 'calendar.events' in query['scope'][0]
    redirect = query['redirect_uri'][0]
    assert redirect.startswith('http://127.0.0.1:')
    with httpx.Client(trust_env=False) as browser:
        assert browser.get(redirect, params={'state': 'errado', 'code': 'codigo'}).status_code == 400
        page = browser.get(redirect, params={'state': query['state'][0], 'code': 'codigo'})
    assert 'Agenda conectada' in page.text
    return api.get('/calendar').json()


def test_demands_with_dates_become_calendar_events(tmp_path, google):
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        vault = api.app.state.vault
        assert api.post('/calendar/sync').status_code == 409
        status = connect(api)
        assert status['connected'] and status['email'] == 'pessoa@example.com'
        assert vault.get(gcal.TOKEN_REF) == 'renovacao' and 'renovacao' not in json.dumps(status)

        dated = api.post('/demands', json={'title': 'Proposta da Ana', 'front_id': 2, 'due': '2026-11-20', 'next_action': 'Enviar valores'}).json()
        api.post('/demands', json={'title': 'Sem data', 'front_id': 1})
        settle(api)
        assert len(google.events) == 1
        event = next(iter(google.events.values()))
        assert event['summary'] == 'Proposta da Ana · Nextlink'
        assert event['start'] == {'date': '2026-11-20'} and event['end'] == {'date': '2026-11-21'}
        assert 'Enviar valores' in event['description']
        assert event['extendedProperties']['private']['monitor_demand'] == str(dated['id'])

        before = google.writes()
        assert api.post('/calendar/sync').json()['created'] == 0
        assert google.writes() == before  # nada mudou: nenhuma chamada à agenda

        api.put(f'/demands/{dated["id"]}', json={**dated, 'stage': 'acompanhar', 'return_date': '2026-12-01'})
        settle(api)
        event = next(iter(google.events.values()))
        assert len(google.events) == 1 and event['summary'].startswith('Retorno: ') and event['start'] == {'date': '2026-12-01'}

        google.events.clear()  # evento apagado direto na agenda é recriado na próxima mudança
        api.put(f'/demands/{dated["id"]}', json={**dated, 'stage': 'acompanhar', 'return_date': '2026-12-02'})
        settle(api)
        assert [e['start'] for e in google.events.values()] == [{'date': '2026-12-02'}]

        api.put(f'/demands/{dated["id"]}', json={**dated, 'stage': 'ganho'})
        settle(api)
        assert google.events == {} and api.get('/calendar').json()['events'] == 0

        api.post('/demands', json={'title': 'Outra', 'front_id': 4, 'due': '2026-11-25'})
        settle(api)
        assert len(google.events) == 1
        assert api.delete('/calendar').status_code == 204
        assert not api.get('/calendar').json()['connected'] and vault.get(gcal.TOKEN_REF) is None
        assert len(google.events) == 1  # desconectar não apaga o que já está na agenda


def test_revoked_access_asks_to_reconnect(tmp_path, google):
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        connect(api)
        gcal._access.clear()
        google.revoked = True
        api.post('/demands', json={'title': 'Prazo', 'front_id': 1, 'due': '2026-11-20'})
        for _ in range(200):
            if api.get('/calendar').json()['error']:
                break
            time.sleep(0.02)
        status = api.get('/calendar').json()
        assert 'Conecte a conta novamente' in status['error'] and not status['connected']


def test_demo_mode_never_touches_the_calendar(tmp_path, google):
    with TestClient(create_app(tmp_path, 'session', True), headers=HEADERS) as api:
        assert api.put('/calendar/client', json=CLIENT).status_code == 409
        assert api.post('/calendar/connect').status_code == 409
    assert google.requests == []
