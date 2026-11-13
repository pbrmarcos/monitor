import json

import httpx
from fastapi.testclient import TestClient

from monitor.assistant import fit_prompt
from monitor.llm_runtime import CONTEXT, KEEP_ALIVE
from monitor.main import create_app


def test_preload_is_private_consistent_and_can_be_disabled(tmp_path, monkeypatch):
    client = httpx.Client
    calls = []

    def handler(request):
        assert 'Authorization' not in request.headers
        calls.append(request.url.path)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'test:4b'}]})
        if request.url.path == '/api/ps':
            return httpx.Response(200, json={'models': []})
        payload = json.loads(request.content)
        assert payload == {'model': 'test:4b', 'messages': [], 'stream': False,
                           'keep_alive': KEEP_ALIVE, 'options': {'num_ctx': CONTEXT}}
        return httpx.Response(200, json={'done': True, 'load_duration': 2000000000})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr('monitor.llm_runtime.httpx.Client', lambda **kw: client(transport=transport, **kw))
    with TestClient(create_app(tmp_path, 'session', False), headers={'Authorization': 'Bearer session'}) as api:
        assert api.get('/settings').json()['keep_model_warm'] is True
        api.put('/settings', json={'model': 'test:4b', 'keep_model_warm': False})
        assert api.app.state.model_runtime.prepare()['enabled'] is False
        assert calls == []
        result = api.post('/ollama/warm').json()
        assert result['state'] == 'ready' and result['load_seconds'] == 2
        assert calls == ['/api/tags', '/api/ps', '/api/chat']


def test_automatic_preload_does_not_replace_other_models(tmp_path, monkeypatch):
    client = httpx.Client

    def handler(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'test:4b'}]})
        assert request.url.path == '/api/ps'
        return httpx.Response(200, json={'models': [{'name': 'another:7b'}]})

    monkeypatch.setattr('monitor.llm_runtime.httpx.Client', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    with TestClient(create_app(tmp_path, 'session', False), headers={'Authorization': 'Bearer session'}) as api:
        api.put('/settings', json={'model': 'test:4b'})
        assert api.app.state.model_runtime.prepare()['state'] == 'deferred'


def test_prompt_budget_keeps_current_question_images_and_critical_instructions():
    messages = [{'role': 'user', 'content': 'old ' * 20000},
                {'role': 'assistant', 'content': 'answer ' * 10000},
                {'role': 'user', 'content': 'Read this image', 'images': ['image-data']}]
    system, fitted = fit_prompt('Critical instructions', 'business data ' * 10000, messages, mode='work')
    assert system.startswith('Critical instructions')
    assert fitted[-1] == messages[-1]
    assert 'Contexto comercial parcial' in system
    assert 'omitida' in system
    assert sum(len(item['content']) for item in fitted) + len(system) < 39000


def test_general_chat_does_not_receive_business_data():
    system, _ = fit_prompt('Instructions', 'private-business-record', [{'role': 'user', 'content': 'Hello'}], mode='general')
    assert 'private-business-record' not in system
