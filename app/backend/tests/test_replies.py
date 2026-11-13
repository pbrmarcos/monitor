import imaplib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from fake_imap import FakeImap, message
from monitor import inbox, replies
from monitor.main import create_app
from monitor.models import Email, EmailDraft, EmailStyle, SentEmail
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}
ACCOUNT = {'front_id': 2, 'address': 'contato@frente02.example', 'host': '127.0.0.1', 'username': 'contato', 'password': 'segredo'}


def plain_imap(host, port):
    return imaplib.IMAP4(host, port)


def sent(to, body, identifier, reply_to=''):
    extra = f'In-Reply-To: {reply_to}\r\n' if reply_to else ''
    raw = message('Marcos <contato@frente02.example>', 'Re: Proposta', body, identifier, extra)
    return raw.replace(b'To: contato@frente01.example', f'To: {to}'.encode())


WRITTEN = {
    1: sent('Ana Souza <ana@cliente.example>', 'Olá, Ana!\r\n\r\nSegue a proposta que combinamos. Qualquer ajuste me avise.\r\n\r\nAbraços,\r\nMarcos', '<s1@x>', '<m1@x>'),
    2: sent('pedro@cliente.example', 'Olá, Pedro!\r\n\r\nConsigo entregar o material na sexta. Pode ser?\r\n\r\nAbraços,\r\nMarcos', '<s2@x>'),
    3: sent('carla@fornecedor.example', 'Bom dia, Carla.\r\n\r\nRecebi o orçamento, obrigado. Retorno até amanhã.\r\n\r\nAbraços,\r\nMarcos', '<s3@x>'),
    4: sent('ana@cliente.example', 'Olá, Ana!\r\n\r\nPerfeito, fechado então. Te mando o contrato hoje.\r\n\r\nAbraços,\r\nMarcos', '<s4@x>'),
}


@pytest.fixture
def imap():
    server = FakeImap({
        1: message('Ana Souza <ana@cliente.example>', 'Dúvida rápida', 'Oi Marcos, conseguiu ver o material que enviei?', '<m1@x>'),
        2: message('Desconhecido <alguem@outro.example>', 'Apresentação', 'Olá, gostaria de apresentar nossa empresa.', '<m2@x>'),
    }, sent=WRITTEN)
    yield server
    server.close()


def make(tmp_path):
    app = create_app(tmp_path, 'session', False, secret_store=MemoryStore(), connector=plain_imap)
    return app, TestClient(app, headers=HEADERS)


def model(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr('monitor.replies.httpx.Client', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))


def test_first_sync_keeps_the_latest_hundred_messages(tmp_path):
    server = FakeImap({uid: message('a@x.example', f'Mensagem {uid}', 'Olá.', f'<m{uid}@x>') for uid in range(1, 151)})
    try:
        app, client = make(tmp_path)
        with client as api:
            api.post('/email-accounts', json={**ACCOUNT, 'port': server.port})
            assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 100
            with Session(app.state.engine) as db:
                subjects = {row.subject for row in db.exec(select(Email)).all()}
            assert 'Mensagem 150' in subjects and 'Mensagem 51' in subjects and 'Mensagem 50' not in subjects
            assert inbox.sync_all(app.state.engine, app.state.vault, plain_imap) == 0
            assert inbox.sync_sent(app.state.engine, 1, app.state.vault, plain_imap) == 0  # servidor sem pasta de enviados
            assert api.get('/email-style').json()[0]['sent_status'] == 'sem_pasta'
    finally:
        server.close()


def test_sent_folder_is_read_only_and_teaches_who_matters(tmp_path, imap):
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        assert inbox.sync_sent(app.state.engine, 1, app.state.vault, plain_imap) == 4
        assert inbox.sync_sent(app.state.engine, 1, app.state.vault, plain_imap) == 0  # incremental
        commands = ' | '.join(imap.commands).upper()
        assert 'EXAMINE "INBOX.SENT"' in commands
        for forbidden in ('STORE', 'APPEND', 'EXPUNGE', 'COPY', 'MOVE', 'DELETE', 'UID SEARCH SINCE'):
            assert forbidden not in commands
        assert 'SELECT' not in commands.replace('EXAMINE', '')
        with Session(app.state.engine) as db:
            rows = db.exec(select(SentEmail).order_by(SentEmail.id)).all()
            assert rows[0].in_reply_to == '<m1@x>' and rows[0].body_text.endswith('Abraços,\nMarcos')
            assert db.exec(select(Email)).all() == []  # enviados não entram na caixa de entrada
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        by_sender = {item['sender']: item['analysis'] for item in api.get('/emails').json()}
        known = by_sender['Ana Souza <ana@cliente.example>']
        assert known['importancia'] == 'importante' and 'Você já escreveu para este remetente.' in known['motivo']
        assert by_sender['Desconhecido <alguem@outro.example>']['importancia'] == 'revisar'


def test_style_is_learned_from_sent_mail_and_respects_manual_edits(tmp_path, imap, monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': '- Cumprimenta com "Olá" e o primeiro nome.\n- Tom informal e direto.'}})

    model(monkeypatch, handler)
    assert replies.stats([raw.decode().split('\r\n\r\n', 1)[1] for raw in WRITTEN.values()]) == {
        'greeting': 'Olá', 'closing': 'Abraços', 'words': 12}
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        style = api.post('/email-style/1/learn').json()
        assert style['sent'] == 4 and style['greeting'] == 'Olá' and style['closing'] == 'Abraços' and style['sent_status'] == 'ok'
        assert 'Tom informal' in style['profile'] and not style['edited']
        prompt = json.dumps(seen[0], ensure_ascii=False)
        assert 'Segue a proposta que combinamos' in prompt and 'segredo' not in prompt

        edited = api.put('/email-style/1', json={'profile': 'Sempre trato o cliente pelo primeiro nome.'}).json()
        assert edited['edited']
        replies.learn(app.state.engine, 1)  # rodada automática não apaga o que o usuário escreveu
        assert api.get('/email-style').json()[0]['profile'] == 'Sempre trato o cliente pelo primeiro nome.'
        assert 'Tom informal' in api.post('/email-style/1/learn').json()['profile']  # pedido explícito reaprende
        assert api.post('/email-style/9/learn').status_code == 404


def test_reply_suggestions_follow_style_and_never_send(tmp_path, imap, monkeypatch):
    seen, answers = [], []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if 'format' not in payload:
            return httpx.Response(200, json={'message': {'content': '- Informal.'}})
        return httpx.Response(200, json={'message': {'content': answers.pop(0)}})

    model(monkeypatch, handler)
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        api.post('/email-style/1/learn')
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        target = next(item for item in api.get('/emails').json() if item['sender'].startswith('Ana'))

        answers[:] = ['isto não é JSON', json.dumps({'opcao_1': 'Olá, Ana! Vi sim. Abraços, Marcos', 'opcao_2': 'Olá, Ana! Vi o material e retorno até [data]. Abraços, Marcos'})]
        result = api.post(f'/emails/{target["id"]}/replies', json={'instruction': 'dizer que vi e retorno depois'})
        assert result.status_code == 200 and len(result.json()['options']) == 2
        prompt = seen[-1]['messages'][1]['content']
        assert 'Saudação mais usada: Olá' in prompt and 'conseguiu ver o material' in prompt and 'dizer que vi e retorno depois' in prompt
        first_example = prompt.split('EXEMPLO 1 DE E-MAIL ESCRITO PELO USUÁRIO:')[1].split('EXEMPLO 2')[0]
        assert 'Ana' in first_example  # respostas anteriores ao mesmo destinatário vêm primeiro
        assert 'segredo' not in json.dumps(seen) and seen[-1]['format']['required'] == ['opcao_1', 'opcao_2']

        answers[:] = [json.dumps({'opcao_1': 'Consigo entregar na sexta.', 'opcao_2': 'Posso entregar na sexta, tudo bem?'})]
        improved = api.post('/emails/improve', json={'text': 'entrego sexta ok', 'draft': 'Olá!\nentrego sexta ok\nAbraços', 'account_id': 1})
        assert improved.json()['options'] == ['Consigo entregar na sexta.', 'Posso entregar na sexta, tudo bem?']
        assert 'TRECHO A REESCREVER:\nentrego sexta ok' in seen[-1]['messages'][1]['content']
        assert api.post('/emails/improve', json={'text': ' '}).status_code in (400, 422)

        answers[:] = ['{}', '{"opcao_1": "", "opcao_2": "x"}']
        assert api.post(f'/emails/{target["id"]}/replies', json={}).status_code == 502
        assert api.post('/emails/999/replies', json={}).status_code == 404

        assert api.get(f'/emails/{target["id"]}/draft').json() == {'body': ''}
        api.put(f'/emails/{target["id"]}/draft', json={'body': 'Olá, Ana! Vi sim.'})
        assert api.get(f'/emails/{target["id"]}/draft').json() == {'body': 'Olá, Ana! Vi sim.'}
        commands = ' | '.join(imap.commands).upper()
        assert 'APPEND' not in commands and 'STORE' not in commands  # nada é gravado nem enviado pelo servidor
        assert api.delete('/email-accounts/1').status_code == 204
        with Session(app.state.engine) as db:
            assert not db.exec(select(SentEmail)).all() and not db.exec(select(EmailDraft)).all() and not db.exec(select(EmailStyle)).all()


def test_offline_model_reports_a_clear_error(tmp_path, imap, monkeypatch):
    def offline(request):
        raise httpx.ConnectError('offline', request=request)

    model(monkeypatch, offline)
    app, client = make(tmp_path)
    with client as api:
        api.post('/email-accounts', json={**ACCOUNT, 'port': imap.port})
        inbox.sync_all(app.state.engine, app.state.vault, plain_imap)
        target = api.get('/emails').json()[0]
        response = api.post(f'/emails/{target["id"]}/replies', json={})
        assert response.status_code == 503 and 'Ollama' in response.json()['detail']
        style = api.post('/email-style/1/learn').json()  # sem IA ficam os padrões contados
        assert style['greeting'] == 'Olá' and style['profile'] == ''
