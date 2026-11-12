import imaplib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from fake_imap import FakeImap, message
from monitor import inbox
from monitor.main import create_app
from monitor.models import AiJob, EmailAccount, Email, EmailAnalysis, Suggestion
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}
ACCOUNT = {'front_id': 2, 'address': 'Contato@Frente02.example', 'host': '127.0.0.1', 'username': 'contato', 'password': 'segredo'}


def plain_imap(host, port):
    return imaplib.IMAP4(host, port)


@pytest.fixture
def imap():
    server = FakeImap({
        1: message('Ana Souza <ana@cliente.example>', 'Site novo',
                   'Olá! Gostaria de receber um orçamento.\r\nPreciso da proposta até 20/11.\r\n-- \r\nAna', '<m1@x>'),
        2: message('Boletim <newsletter@loja.example>', 'Ofertas', 'Promoções da semana.', '<m2@x>',
                   'List-Unsubscribe: <mailto:sair@loja.example>\r\n'),
    })
    yield server
    server.close()


def make(tmp_path, vault=None):
    app = create_app(tmp_path, 'session', False, secret_store=vault or MemoryStore(), connector=plain_imap)
    return app, TestClient(app, headers=HEADERS)


def ollama(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr('monitor.ai.httpx.Client', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))


def offline(request):
    raise httpx.ConnectError('offline', request=request)


def test_read_only_collection_rules_and_suggestion(tmp_path, imap, monkeypatch):
    ollama(monkeypatch, offline)
    vault = MemoryStore()
    app, client = make(tmp_path, vault)
    payload = {**ACCOUNT, 'port': imap.port}
    with client as api:
        assert api.post('/email-accounts/test', json={**payload, 'password': 'errada'}).status_code == 400
        assert api.post('/email-accounts', json={**payload, 'password': 'errada'}).status_code == 400
        created = api.post('/email-accounts', json=payload)
        assert created.status_code == 201 and 'password' not in created.text and 'segredo' not in created.text
        assert api.post('/email-accounts', json=payload).status_code == 409
        assert vault.values == {'imap:contato@frente02.example': 'segredo'}
        with Session(app.state.engine) as db:
            stored = db.exec(select(EmailAccount)).one()
            assert 'segredo' not in json.dumps(stored.model_dump(), default=str)
        assert api.post('/emails/sync').json() == {'new': 2}
        assert api.post('/emails/sync').json() == {'new': 0}

        emails = {item['subject']: item for item in api.get('/emails').json()}
        budget, promo = emails['Site novo'], emails['Ofertas']
        assert budget['front_id'] == 2 and budget['body'].endswith('até 20/11.')  # assinatura removida
        assert budget['analysis']['importancia'] == 'acao' and budget['analysis']['provisional']
        assert budget['analysis']['prazo_iso'].endswith('-11-20')
        assert promo['analysis']['importancia'] == 'info' and promo['analysis']['categoria'] == 'publicidade'
        assert api.get('/ai/status').json() == {'pending': 2, 'failed': 0}  # Ollama fora do ar: fila preservada

        suggestion = api.get('/suggestions').json()
        assert len(suggestion) == 1 and suggestion[0]['email_id'] == budget['id']
        demand = api.post(f"/suggestions/{suggestion[0]['id']}/accept").json()
        assert demand['channel'] == 'email' and demand['created_by'] == 'ia' and demand['origin_ref'] == f"email:{budget['id']}"
        assert api.get('/suggestions').json() == []
        linked = {item['subject']: item['demand_id'] for item in api.get('/emails').json()}
        assert linked == {'Site novo': demand['id'], 'Ofertas': None}

        imap.messages[3] = message('Pedro <pedro@x.example>', 'Novo', 'Olá.', '<m3@x>')
        assert api.post('/emails/sync').json() == {'new': 1}
        assert api.delete(f"/email-accounts/{created.json()['id']}").status_code == 204
        assert vault.values == {} and api.get('/emails').json() == []

    commands = ' | '.join(imap.commands).upper()
    assert 'EXAMINE' in commands and 'BODY.PEEK' in commands
    for forbidden in ('STORE', 'SELECT ', 'EXPUNGE', 'COPY', 'MOVE', 'DELETE', 'APPEND'):
        assert forbidden not in commands


def test_ai_queue_validates_retries_and_learns_from_corrections(tmp_path, imap, monkeypatch):
    calls = []
    answer = {'categoria': 'cliente', 'importancia': 'importante', 'motivo': 'Cliente pede retorno.', 'resumo': 'Pedido.',
              'acao_sugerida': 'Enviar proposta', 'prazo_texto': None, 'prazo_iso': None, 'trecho_prazo': None,
              'criar_demanda': True, 'confianca': 0.9}

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert 'segredo' not in request.content.decode() and body['format']['properties']['categoria']
        if len(calls) == 1:
            return httpx.Response(200, json={'message': {'content': 'isto não é JSON'}})
        return httpx.Response(200, json={'message': {'content': json.dumps(answer)}})

    ollama(monkeypatch, handler)
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        assert inbox.process_queue(app.state.engine) == 2
        assert len(calls) == 3 and calls[0]['think'] is False  # uma nova tentativa após JSON inválido
        emails = {item['subject']: item for item in api.get('/emails').json()}
        budget = emails['Site novo']['analysis']
        assert not budget['provisional'] and budget['importancia'] == 'acao' and budget['categoria'] == 'cliente'
        assert api.get('/suggestions').json()[0]['title'] == 'Enviar proposta'
        assert api.get('/ai/status').json() == {'pending': 0, 'failed': 0}

        promo = emails['Ofertas']
        assert api.post(f"/emails/{promo['id']}/correction", json={'value': 'nao_importante'}).json()['importancia'] == 'info'
        with Session(app.state.engine) as db:
            db.add(AiJob(ref_id=emails['Site novo']['id']))
            db.commit()
        calls.clear()
        assert inbox.process_queue(app.state.engine) == 1
        assert len(calls[0]['messages']) == 4  # sistema + exemplo corrigido (pergunta e resposta) + mensagem


def test_demo_mode_has_sample_inbox_and_blocks_real_accounts(tmp_path):
    with TestClient(create_app(tmp_path, 'session', True), headers=HEADERS) as api:
        assert len(api.get('/emails').json()) == 4 and len(api.get('/suggestions').json()) == 1
        assert api.post('/email-accounts', json={**ACCOUNT, 'port': 993}).status_code == 409


def test_incremental_backlog_is_drained_without_skipping(tmp_path, imap):
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 2
        for uid in range(3, 454):
            imap.messages[uid] = message('a@x.example', 'Novo contato', 'Olá.', f'<m{uid}@x>')
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 200
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 200
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 51
        with Session(app.state.engine) as db:
            assert len(db.exec(select(Email)).all()) == 453


def test_partial_fetch_does_not_advance_cursor(tmp_path, imap):
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        imap.omit_uids.add(1)
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 0
        with Session(app.state.engine) as db:
            assert db.exec(select(EmailAccount)).one().last_uids == '{}'
        imap.omit_uids.clear()
        assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 2


def test_historical_email_uses_message_date_for_relative_deadlines(tmp_path, imap):
    imap.messages = {1: message('ana@x.example', 'Contrato', 'Envie o contrato até amanhã.', '<old@x>').replace(
        b'Thu, 12 Nov 2026', b'Sun, 01 Nov 2026')}
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        assert api.get('/emails').json()[0]['analysis']['prazo_iso'] == '2026-11-02'


def test_suggestion_is_withdrawn_after_analysis_downgrade(tmp_path, imap, monkeypatch):
    from monitor.ai import Analysis
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        with Session(app.state.engine) as db:
            item = db.exec(select(Email).where(Email.subject == 'Ofertas')).one()
            identifier = item.id
            db.add(Suggestion(email_id=item.id, front_id=2, title='Sugestão provisória'))
            db.commit()
        monkeypatch.setattr(inbox.ai, 'analyze', lambda *a: Analysis(categoria='informativo', importancia='info',
            motivo='Sem ação.', resumo='Informação.', criar_demanda=False, confianca=0.9))
        inbox.process_queue(app.state.engine)
        assert all(s['email_id'] != identifier for s in api.get('/suggestions').json())


def test_correction_during_model_request_is_preserved(tmp_path, imap, monkeypatch):
    from monitor.ai import Analysis
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)

        def analyze(sender, *args):
            with Session(app.state.engine) as db:
                row = db.exec(select(Email).where(Email.sender == sender)).one()
                analysis = db.get(EmailAnalysis, row.id)
                analysis.correcao, analysis.importancia = 'nao_importante', 'info'
                db.add(analysis)
                db.commit()
            return Analysis(categoria='cliente', importancia='acao', motivo='Retorno.', resumo='Pedido.', confianca=0.9)

        monkeypatch.setattr(inbox.ai, 'analyze', analyze)
        inbox.process_queue(app.state.engine)
        assert all(e['analysis']['importancia'] == 'info' for e in api.get('/emails').json())
