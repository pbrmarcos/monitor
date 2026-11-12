from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor.main import create_app
from monitor import sites
from monitor.models import Notice, SiteCheck, now


def test_site_incident_recovery_ssl_and_restart(tmp_path):
    app = create_app(tmp_path, 'session', False)
    headers = {'Authorization': 'Bearer session'}
    state = {'status': 503, 'body': 'Indisponível'}
    transport = httpx.MockTransport(lambda request: httpx.Response(state['status'], text=state['body']))
    with TestClient(app, headers=headers) as api:
        payload = dict(name='Site', url='https://example.org', front_id=1, expected_text='Contato')
        identifier = api.post('/sites', json=payload).json()['id']
        for _ in range(2):
            assert sites.check_all(app.state.engine, identifier, transport=transport, certificate=lambda _: now() + timedelta(days=10))
        history = api.get(f'/sites/{identifier}/history').json()
        assert len(history['checks']) == 2 and len(history['incidents']) == 1
        assert history['incidents'][0]['closed_at'] is None
        with Session(app.state.engine) as db:
            assert len(db.exec(select(Notice)).all()) == 2  # incident and one expiry warning
        state.update(status=200, body='Contato')
        sites.check_all(app.state.engine, identifier, transport=transport, certificate=lambda _: now() + timedelta(days=10))
        result = api.get('/sites').json()[0]
        assert result['samples'] == 3 and result['success_percent'] == 33.33
        assert result['latest']['checked_at'].endswith(('+00:00', 'Z'))
        assert api.get(f'/sites/{identifier}/history').json()['incidents'][0]['closed_at']
    with TestClient(create_app(tmp_path, 'session', False), headers=headers) as api:
        assert api.get('/sites').json()[0]['samples'] == 3
        assert len(api.get('/notifications').json()) == 3
        api.put(f'/sites/{identifier}', json={**payload, 'expected_text': 'Outro texto'})
        assert api.get('/sites').json()[0]['samples'] == 0  # no mixing of distinct rules
        assert api.delete(f'/sites/{identifier}').status_code == 204
        assert api.get('/sites').json() == []


def test_probe_redirect_content_timeout_and_http():
    site = sites.Site(name='Teste', url='http://example.org', front_id=1, expected_text='Esperado')
    def respond(request):
        if request.url.scheme == 'http':
            return httpx.Response(301, headers={'Location': 'https://example.org'})
        return httpx.Response(200, text='ESPERADO')
    urls = []
    result = sites.probe(site, transport=httpx.MockTransport(respond), certificate=lambda url: urls.append(url))
    assert result['ok'] and urls == ['https://example.org']
    result = sites.probe(site, transport=httpx.MockTransport(lambda _: httpx.Response(200, text='erro')), certificate=lambda _: None)
    assert not result['ok'] and 'Texto' in result['detail']
    def timeout(request):
        raise httpx.ReadTimeout('private URL must not leak')
    result = sites.probe(site, transport=httpx.MockTransport(timeout))
    assert not result['ok'] and result['detail'] == 'Tempo de resposta esgotado.'
    result = sites.probe(site, transport=httpx.MockTransport(lambda _: httpx.Response(200, text='Esperado')))
    assert result['ok'] and result['ssl_expires'] is None  # plain HTTP doesn't claim TLS


def test_auth_validation_pause_demo_and_retention(tmp_path):
    app = create_app(tmp_path, 'session', False)
    payload = dict(name='Site', url='https://example.org', front_id=1)
    with TestClient(app) as api:
        assert api.get('/sites').status_code == 401
        api.headers.update({'Authorization': 'Bearer session'})
        for url in ['file:///etc/passwd', 'https://user:password@example.org', 'https://example.org:bad', 'https://example.org/#token']:
            assert api.post('/sites', json={**payload, 'url': url}).status_code == 422
        identifier = api.post('/sites', json={**payload, 'enabled': False}).json()['id']
        assert api.post(f'/sites/{identifier}/check').status_code == 409
        assert len(api.get('/sites/suggestions').json()) == 4
        with Session(app.state.engine) as db:
            db.add(SiteCheck(site_id=identifier, ok=True, checked_at=now() - timedelta(days=40)))
            db.commit()
        api.put(f'/sites/{identifier}', json=payload)
        sites.check_all(app.state.engine, transport=httpx.MockTransport(lambda _: httpx.Response(200)), certificate=lambda _: None)
        assert len(api.get(f'/sites/{identifier}/history').json()['checks']) == 1
    with TestClient(create_app(tmp_path, 'session', True), headers={'Authorization': 'Bearer session'}) as api:
        assert api.post('/sites', json=payload).status_code == 409
