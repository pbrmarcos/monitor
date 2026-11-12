import json

import httpx
from fastapi.testclient import TestClient

from monitor.main import create_app
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}


def test_chat_streams_answer_grounded_in_local_data(tmp_path, monkeypatch):
    real_client, seen = httpx.Client, []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if 'think' in payload:
            return httpx.Response(400, json={'error': 'does not support thinking'})
        lines = [{'message': {'content': 'Priorize a proposta '}}, {'message': {'content': '[D1].'}}, {'done': True}]
        return httpx.Response(200, text='\n'.join(json.dumps(line) for line in lines))

    monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        api.app.state.vault.set('imap:conta@example.com', 'senha-secreta')
        api.post('/demands', json={'title': 'Proposta da Ana', 'front_id': 2, 'due': '2026-11-20', 'next_action': 'Enviar valores'})
        api.post('/demands', json={'title': 'Negócio fechado', 'front_id': 1, 'stage': 'ganho'})
        response = api.post('/assistant/chat', json={'messages': [{'role': 'user', 'content': 'O que priorizar?'}]})
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert ''.join(line.get('delta', '') for line in lines) == 'Priorize a proposta [D1].' and lines[-1] == {'done': True}
        system = seen[-1]['messages'][0]['content']
        assert '[D1] Proposta da Ana | Nextlink' in system and 'prazo 2026-11-20' in system and 'Enviar valores' in system
        assert 'Negócio fechado' not in system and 'senha-secreta' not in json.dumps(seen)
        assert 'think' in seen[0] and 'think' not in seen[1]  # repete sem o parâmetro recusado
        assert seen[-1]['messages'][-1] == {'role': 'user', 'content': 'O que priorizar?'}
        assert api.post('/assistant/chat', json={'messages': [{'role': 'assistant', 'content': 'oi'}]}).status_code == 400
        assert api.post('/assistant/chat', json={'messages': []}).status_code == 422


def test_chat_reports_offline_ollama_and_missing_model(tmp_path, monkeypatch):
    real_client = httpx.Client

    def offline(request):
        raise httpx.ConnectError('offline', request=request)

    question = {'messages': [{'role': 'user', 'content': 'Oi'}]}
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(offline), **kw))
        assert 'Ollama' in json.loads(api.post('/assistant/chat', json=question).text)['error']
        missing = httpx.MockTransport(lambda request: httpx.Response(404, json={'error': 'model not found'}))
        monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real_client(transport=missing, **kw))
        assert 'não está instalado' in json.loads(api.post('/assistant/chat', json=question).text)['error']


def test_general_chat_has_no_business_context_and_accepts_history(tmp_path, monkeypatch):
    real_client, seen = httpx.Client, []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=json.dumps({'message': {'content': 'Vamos falar de astronomia.'}}) + '\n' + json.dumps({'done': True}))
    monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    def forbidden_context(*args):
        raise AssertionError('A conversa geral não pode coletar dados das frentes.')
    monkeypatch.setattr('monitor.assistant.context', forbidden_context)
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        api.post('/demands', json={'title': 'Proposta confidencial', 'front_id': 1})
        history = [{'role': 'user', 'content': 'Vamos falar de astronomia?'}, {'role': 'assistant', 'content': 'Claro.'}, {'role': 'user', 'content': 'Explique as estrelas.'}]
        response = api.post('/assistant/chat', json={'mode': 'general', 'messages': history})
        assert response.status_code == 200 and 'astronomia' in response.text
        system = seen[0]['messages'][0]['content']
        assert 'conversa geral' in system and 'DADOS DO MONITOR' not in system
        assert 'Proposta confidencial' not in json.dumps(seen)
        assert seen[0]['messages'][1:] == history
        assert api.post('/assistant/chat', json={'mode': 'unknown', 'messages': history}).status_code == 422
