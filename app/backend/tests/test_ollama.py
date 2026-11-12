import httpx
from fastapi.testclient import TestClient
from monitor.main import create_app


def test_model_configuration_and_pull_without_forwarding_session_token(tmp_path, monkeypatch):
    real_client = httpx.AsyncClient

    def handler(request):
        assert 'Authorization' not in request.headers
        assert request.url.host == '127.0.0.1'
        if request.url.path == '/api/version':
            return httpx.Response(200, json={'version': 'test'})
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'test:4b'}]})
        if request.url.path == '/api/pull':
            return httpx.Response(200, text='{"status":"downloading","total":100,"completed":50}\n{"status":"success"}\n')
        raise AssertionError(request.url.path)

    monkeypatch.setattr('monitor.main.httpx.AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    headers = {'Authorization': 'Bearer local-session'}
    with TestClient(create_app(tmp_path, 'local-session', False), headers=headers) as api:
        assert api.put('/settings', json={'model': 'test:4b'}).status_code == 200
        assert api.get('/settings').json()['model'] == 'test:4b'
        assert api.put('/settings', json={'model': 'not a model; command'}).status_code == 422
        assert api.get('/ollama').json() == {'available': True, 'models': ['test:4b']}
        response = api.post('/ollama/pull', json={'model': 'test:4b'})
        assert response.status_code == 200
        assert '"completed":50' in response.text
        assert '"status":"success"' in response.text


def test_offline_ollama_does_not_block_demands(tmp_path, monkeypatch):
    real_client = httpx.AsyncClient

    def offline(request):
        raise httpx.ConnectError('offline', request=request)

    monkeypatch.setattr('monitor.main.httpx.AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(offline), **kwargs))
    with TestClient(create_app(tmp_path, 'session', False), headers={'Authorization': 'Bearer session'}) as api:
        assert api.get('/ollama').json() == {'available': False, 'models': []}
        assert api.post('/demands', json={'title': 'Sem IA', 'front_id': 1}).status_code == 201
