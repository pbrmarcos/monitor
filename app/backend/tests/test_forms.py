import importlib.util
from pathlib import Path
from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor import forms
from monitor.main import create_app
from monitor.models import Demand, Email, EmailAccount, FormEntry, Notice, Setting, now
from monitor.secrets_store import MemoryStore

spec = importlib.util.spec_from_file_location('monitor_test_relay', Path(__file__).resolve().parents[3] / 'relay/main.py')
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)
APP_TOKEN = 'app-' + 'a' * 40
SITE_TOKEN = 'site-' + 'b' * 40
PAYLOAD = dict(submission_id='test-send-001', name='Ana', email='ana@example.org', subject='Orçamento', message='Preciso de uma proposta.')
AUTH = {'Authorization': 'Bearer session'}


def test_relay_auth_idempotence_ack_test_and_restart(tmp_path):
    database = tmp_path / 'relay.db'
    app = relay.create_app(database, APP_TOKEN, {'1': SITE_TOKEN})
    with TestClient(app) as api:
        assert api.get('/events').status_code == 401
        assert api.post('/forms/1', json=PAYLOAD, headers={'Authorization': f'Bearer {APP_TOKEN}'}).status_code == 401
        headers = {'Authorization': f'Bearer {SITE_TOKEN}'}
        assert api.post('/forms/1', json=PAYLOAD, headers={**headers, 'X-Monitor-Test': '1'}).json()['test']
        reader = {'Authorization': f'Bearer {APP_TOKEN}'}
        assert api.get('/events', headers=reader).json() == []
        first = api.post('/forms/1', json=PAYLOAD, headers=headers)
        assert first.status_code == 202
        assert api.post('/forms/1', json=PAYLOAD, headers=headers).json() == first.json()
        assert api.post('/forms/1', json={**PAYLOAD, 'message': 'Outro envio'}, headers=headers).status_code == 409
        assert len(api.get('/events', headers=reader).json()) == 1
        assert api.post('/events/ack', json={'ids': [first.json()['id']]}, headers=headers).status_code == 401
        assert api.post('/forms/1', content=b'x' * 64001).status_code == 413
        invalid = api.post('/forms/1', json={**PAYLOAD, 'email': 'invalid-private-data'}, headers=headers)
        assert invalid.status_code == 422 and 'private-data' not in invalid.text
    with TestClient(relay.create_app(database, APP_TOKEN, {'1': SITE_TOKEN})) as api:
        events = api.get('/events', headers=reader).json()
        assert len(events) == 1
        assert api.post('/events/ack', json={'ids': [events[0]['id']]}, headers=reader).status_code == 204
        assert api.get('/events', headers=reader).json() == []


def test_relay_rate_limit(tmp_path):
    with TestClient(relay.create_app(tmp_path / 'r.db', APP_TOKEN, {'1': SITE_TOKEN})) as api:
        headers = {'Authorization': f'Bearer {SITE_TOKEN}', 'X-Monitor-Test': '1'}
        for _ in range(30):
            assert api.post('/forms/1', json=PAYLOAD, headers=headers).status_code == 202
        assert api.post('/forms/1', json=PAYLOAD, headers=headers).status_code == 429


def test_collection_commit_before_ack_retry_and_accept_once(tmp_path):
    vault = MemoryStore()
    app = create_app(tmp_path / 'local', 'session', False, secret_store=vault)
    remote = relay.create_app(tmp_path / 'remote.db', APP_TOKEN, {'1': SITE_TOKEN})
    with TestClient(app, headers=AUTH) as api, TestClient(remote) as remote_api:
        api.post('/sites', json={'name': 'Site', 'url': 'https://example.org', 'front_id': 2})
        assert api.put('/relay', json={'url': 'http://unsafe.org', 'token': APP_TOKEN}).status_code == 422
        assert api.put('/relay', json={'url': 'https://relay.example.org', 'token': APP_TOKEN}).json()['has_token']
        assert APP_TOKEN not in api.get('/relay').text
        remote_api.post('/forms/1', json=PAYLOAD, headers={'Authorization': f'Bearer {SITE_TOKEN}'})
        state = {'fail_ack': True}
        def transport(request):
            if request.url.path == '/events/ack':
                with Session(app.state.engine) as db:
                    assert len(db.exec(select(FormEntry)).all()) == 1  # durable before ACK
                if state['fail_ack']:
                    return httpx.Response(503)
            response = remote_api.request(request.method, request.url.raw_path.decode(), headers=dict(request.headers), content=request.content)
            return httpx.Response(response.status_code, content=response.content)
        assert not forms.sync(app.state.engine, vault, transport=httpx.MockTransport(transport))
        assert len(api.get('/forms').json()) == 1
        state['fail_ack'] = False
        assert forms.sync(app.state.engine, vault, transport=httpx.MockTransport(transport))
        entries = api.get('/forms').json()
        assert len(entries) == 1
        assert len([n for n in api.get('/notifications').json() if n['kind'] == 'formulario']) == 1
        identifier = entries[0]['id']
        first = api.post(f'/forms/{identifier}/accept').json()
        assert api.post(f'/forms/{identifier}/accept').json() == first
        demands = api.get('/demands').json()
        assert len(demands) == 1 and demands[0]['front_id'] == 2
        assert demands[0]['channel'] == 'formulario'
        assert api.put(f"/demands/{demands[0]['id']}", json={k:v for k,v in demands[0].items() if k not in ('id','created_at','created_by')}).status_code == 200
        api.put('/relay', json={'url': ''})
        assert not vault.get('relay:token') and len(api.get('/forms').json()) == 1


def test_unmapped_site_not_acknowledged_and_no_secret_in_db(tmp_path):
    vault = MemoryStore()
    app = create_app(tmp_path, 'session', False, secret_store=vault)
    with TestClient(app, headers=AUTH) as api:
        api.put('/relay', json={'url': 'https://relay.example.org', 'token': APP_TOKEN})
        event = {**PAYLOAD, 'site_id': 999, 'received_at': now().isoformat(), 'id': 1}
        requests = []
        def handle(request):
            requests.append(request.method)
            return httpx.Response(200, json=[event])
        assert not forms.sync(app.state.engine, vault, transport=httpx.MockTransport(handle))
        assert requests == ['GET']
        assert api.get('/forms').json() == []
        with Session(app.state.engine) as db:
            assert APP_TOKEN not in str(db.exec(select(Setting)).all())


def test_conservative_cross_channel_deduplication(tmp_path):
    app = create_app(tmp_path, 'session', False)
    with TestClient(app, headers=AUTH) as api:
        with Session(app.state.engine) as db:
            entry = FormEntry(source_key='1', site_id=1, front_id=1, name='Ana', email='ana@example.org', subject='Contato', message=PAYLOAD['message'], received_at=now())
            account = EmailAccount(front_id=1, address='contato@example.org', host='imap.example.org', username='u', keyring_ref='test')
            db.add(account); db.add(entry); db.flush()
            email = Email(account_id=account.id, message_id='test', sender='Ana <ana@example.org>', body_text=PAYLOAD['message'], date=now())
            db.add(email); db.commit(); db.refresh(email); db.refresh(entry)
            email_id, entry_id = email.id, entry.id
        demand = api.post(f'/forms/{entry_id}/accept').json()
        result = api.post('/demands', json={'title':'Contato', 'front_id':1, 'channel':'email', 'origin_ref':f'email:{email_id}'}).json()
        assert result['id'] == demand['demand_id'] and len(api.get('/demands').json()) == 1
        with Session(app.state.engine) as db:
            email = db.get(Email, email_id)
            assert forms.demand_for_email(db, email, 2) is None  # same contact, another business
            email.body_text = 'Outro pedido'
            assert forms.demand_for_email(db, email, 1) is None
            email.body_text = PAYLOAD['message']; email.date = now() - timedelta(hours=1)
            assert forms.demand_for_email(db, email, 1) is None


def test_form_reuses_email_demand(tmp_path):
    app = create_app(tmp_path, 'session', False)
    with TestClient(app, headers=AUTH) as api:
        with Session(app.state.engine) as db:
            email = Email(account_id=1, message_id='source', sender='ana@example.org', body_text=PAYLOAD['message'], date=now())
            db.add(email); db.flush()
            demand = Demand(title='Pedido', front_id=1, channel='email', origin_ref=f'email:{email.id}')
            db.add(demand)
            entry = FormEntry(source_key='entry', site_id=1, front_id=1, name='Ana', email='ana@example.org', subject='Pedido', message=PAYLOAD['message'], received_at=now())
            db.add(entry); db.commit(); db.refresh(entry); db.refresh(demand)
            entry_id, demand_id = entry.id, demand.id
        result = api.post(f'/forms/{entry_id}/accept').json()
        assert result == {'demand_id': demand_id, 'status': 'duplicada'}
        assert len(api.get('/demands').json()) == 1
