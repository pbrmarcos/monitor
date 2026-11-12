"""Coleta IMAP somente leitura: EXAMINE e BODY.PEEK, sem marcar, mover ou apagar mensagens."""
import email
import email.policy
import hashlib
import imaplib
import re
import socket
import ssl
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

FOLDER = 'INBOX'
FIRST_SYNC_DAYS = 30
FIRST_SYNC_LIMIT = 200
FETCH_BYTES = 262144
BODY_LIMIT = 20000
QUOTE_START = re.compile(
    r'^(-{2,}\s*(mensagem original|original message|forwarded message|mensagem encaminhada)\s*-{2,}'
    r'|em .{5,80} escreveu:|on .{5,80} wrote:|de: .+|from: .+)\s*$', re.I)


class MailError(Exception):
    """Falha de coleta com mensagem pronta para a interface, sem credenciais."""


def connect(host: str, port: int):
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=20)


def _open(host: str, port: int, username: str, password: str, connector):
    try:
        connection = connector(host, port)
    except (OSError, ssl.SSLError, socket.timeout, imaplib.IMAP4.error):
        raise MailError('Não foi possível conectar ao servidor. Confira o endereço, a porta e a conexão SSL.') from None
    try:
        connection.login(username, password)
    except imaplib.IMAP4.error:
        _close(connection)
        raise MailError('O servidor recusou o usuário ou a senha.') from None
    except (OSError, socket.timeout):
        _close(connection)
        raise MailError('A conexão caiu durante a autenticação.') from None
    return connection


def _close(connection):
    try:
        connection.logout()
    except Exception:
        pass


def _examine(connection) -> int:
    status, _ = connection.select(FOLDER, readonly=True)
    if status != 'OK':
        raise MailError('Não foi possível abrir a caixa de entrada em modo de leitura.')
    validity = connection.response('UIDVALIDITY')[1]
    return int(validity[0]) if validity and validity[0] else 0


def check_login(host: str, port: int, username: str, password: str, connector=connect) -> None:
    connection = _open(host, port, username, password, connector)
    try:
        _examine(connection)
    except (imaplib.IMAP4.error, OSError):
        raise MailError('Conexão aceita, mas a caixa de entrada não pôde ser lida.') from None
    finally:
        _close(connection)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.skip += 1
        elif tag in ('br', 'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def clean_body(text: str) -> str:
    """Remove citações de respostas anteriores e a assinatura; mantém só o conteúdo novo."""
    lines = []
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        stripped = line.strip()
        if stripped == '--' or line.rstrip('\n') == '-- ' or QUOTE_START.match(stripped):
            break
        if stripped.startswith('>'):
            continue
        lines.append(' '.join(stripped.split()))
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()[:BODY_LIMIT]


def _part_text(part) -> str:
    try:
        return part.get_content()
    except Exception:
        payload = part.get_payload(decode=True) or b''
        return payload.decode('utf-8', 'replace')


def parse_message(raw: bytes, uid: int, flags: str, structure: str) -> dict:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    plain = html = ''
    attachments = 'attachment' in structure.lower()
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_content_disposition() == 'attachment' or part.get_filename():
            attachments = True
        elif part.get_content_type() == 'text/plain' and not plain:
            plain = _part_text(part)
        elif part.get_content_type() == 'text/html' and not html:
            html = _part_text(part)
    if not plain.strip() and html:
        parser = _Text()
        parser.feed(html)
        plain = ''.join(parser.parts)
    try:
        when = parsedate_to_datetime(str(message['Date']))
        when = when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        when = None
    sender = str(message['From'] or '')
    bulk = bool(message['List-Unsubscribe'] or str(message['Precedence'] or '').lower() in ('bulk', 'list', 'junk')
                or re.search(r'\b(no-?reply|newsletter|marketing|mailer)\b', sender.lower()))
    return {
        'message_id': str(message['Message-ID'] or '').strip() or f'<sem-id-{hashlib.sha256(raw).hexdigest()}@{FOLDER}>',
        'sender': sender[:300], 'recipients': str(message['To'] or '')[:500],
        'subject': str(message['Subject'] or '(sem assunto)')[:300], 'date': when,
        'body_text': clean_body(plain), 'has_attachments': attachments, 'bulk': bulk,
        'folder': FOLDER, 'uid': uid, 'flags': flags,
    }


def fetch_new(host: str, port: int, username: str, password: str, state: dict, connector=connect) -> tuple[list[dict], dict]:
    """Busca mensagens novas da caixa de entrada e devolve o novo marcador de UID."""
    connection = _open(host, port, username, password, connector)
    try:
        validity = _examine(connection)
        known = state.get(FOLDER, {})
        last = known.get('uid', 0) if known.get('uidvalidity') == validity else 0
        if last:
            status, data = connection.uid('SEARCH', None, 'UID', f'{last + 1}:*')
        else:
            since = (datetime.now(timezone.utc) - timedelta(days=FIRST_SYNC_DAYS)).strftime('%d-%b-%Y')
            status, data = connection.uid('SEARCH', None, 'SINCE', since)
        if status != 'OK':
            raise MailError('O servidor não respondeu à busca de mensagens.')
        candidates = sorted(int(value) for value in (data[0] or b'').split() if int(value) > last)
        # The initial import is intentionally bounded to recent messages. Later
        # batches must drain oldest-first, otherwise a busy inbox loses demand sources.
        uids = candidates[:FIRST_SYNC_LIMIT] if last else candidates[-FIRST_SYNC_LIMIT:]
        messages = []
        for start in range(0, len(uids), 25):
            chunk = ','.join(str(uid) for uid in uids[start:start + 25])
            status, data = connection.uid('FETCH', chunk, f'(UID FLAGS BODYSTRUCTURE BODY.PEEK[]<0.{FETCH_BYTES}>)')
            if status != 'OK':
                raise MailError('O servidor não entregou as mensagens.')
            index = 0
            while index < len(data):
                item = data[index]
                index += 1
                if not isinstance(item, tuple):
                    continue
                meta = item[0].decode('utf-8', 'replace')
                if index < len(data) and isinstance(data[index], bytes):
                    meta += data[index].decode('utf-8', 'replace')
                uid = re.search(r'UID (\d+)', meta)
                if not uid:
                    continue
                flags = re.search(r'FLAGS \(([^)]*)\)', meta)
                messages.append(parse_message(item[1], int(uid.group(1)), flags.group(1) if flags else '', meta))
        if {item['uid'] for item in messages} != set(uids):
            raise MailError('A coleta veio incompleta. O Monitor tentará novamente sem avançar o marcador.')
        return messages, {**state, FOLDER: {'uidvalidity': validity, 'uid': max(uids, default=last)}}
    except (imaplib.IMAP4.error, OSError, socket.timeout):
        raise MailError('A conexão com o servidor de e-mail falhou durante a coleta.') from None
    finally:
        _close(connection)
