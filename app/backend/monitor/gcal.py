"""Demandas com data viram eventos de dia inteiro no Google Agenda do usuário.

Sentido único: o Monitor grava e atualiza os próprios eventos; nada é lido da agenda.
O token de acesso e o segredo do cliente OAuth ficam no Gerenciador de Credenciais do Windows.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
import uuid
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from sqlmodel import Session, select

from . import prefs
from .models import CalendarLink, ReminderCalendarLink, Reminder, Demand, Setting, now, as_utc

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
EVENTS_URL = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
SCOPES = 'https://www.googleapis.com/auth/calendar.events email'
SECRET_REF = 'google:client_secret'
TOKEN_REF = 'google:refresh_token'
STAGES = {'novo': 'Novo', 'qualificacao': 'Em qualificação', 'preparar_proposta': 'Preparar proposta',
          'proposta_enviada': 'Proposta enviada', 'acompanhar': 'Acompanhar'}
TRANSPORT = None  # substituído nos testes
_lock = threading.Lock()
_access: dict = {}
_pending: dict = {}


class CalendarError(Exception):
    pass


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(20, connect=5), transport=TRANSPORT)


def _get(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else ''


def _put(db: Session, key: str, value: str) -> None:
    db.merge(Setting(key=key, value=value))


def status(db: Session, vault) -> dict:
    return {
        'client_id': _get(db, 'google_client_id'),
        'configured': bool(_get(db, 'google_client_id') and vault.get(SECRET_REF)),
        'connected': bool(vault.get(TOKEN_REF)),
        'email': _get(db, 'google_email'),
        'last_sync': _get(db, 'google_last_sync') or None,
        'error': _get(db, 'google_error'),
        'events': len(db.exec(select(CalendarLink).where(CalendarLink.fingerprint != '')).all()) + len(db.exec(select(ReminderCalendarLink).where(ReminderCalendarLink.fingerprint != '')).all()),
    }


def disconnect(engine, vault) -> None:
    """Remove o acesso local. Os eventos já criados permanecem na agenda."""
    vault.delete(TOKEN_REF)
    _access.clear()
    with Session(engine) as db:
        for link in db.exec(select(CalendarLink)).all():
            db.delete(link)
        for link in db.exec(select(ReminderCalendarLink)).all():
            db.delete(link)
        for key in ('google_email', 'google_error', 'google_last_sync'):
            if row := db.get(Setting, key):
                db.delete(row)
        db.commit()


# ---- Autorização (OAuth com retorno em 127.0.0.1 e PKCE) -----------------

PAGE = ('<!doctype html><meta charset="utf-8"><title>Monitor</title>'
        '<body style="font-family:sans-serif;padding:48px;color:#0D213A"><h1>{title}</h1><p>{text}</p></body>')


def start_authorization(engine, vault, opener=webbrowser.open, wait: float = 300) -> str:
    with Session(engine) as db:
        client_id = _get(db, 'google_client_id')
    client_secret = vault.get(SECRET_REF)
    if not client_id or not client_secret:
        raise CalendarError('Informe primeiro o ID e a chave secreta do cliente OAuth.')
    if previous := _pending.pop('server', None):
        previous.server_close()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # nada de códigos de autorização em logs
            pass

        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if query.get('state', [''])[0] != state:
                self.send_error(400)
                return
            try:
                if 'code' not in query:
                    raise CalendarError('A autorização foi cancelada.')
                _finish(engine, vault, client_id, client_secret, query['code'][0], verifier, redirect)
                title, text = 'Agenda conectada', 'Pode fechar esta janela e voltar ao Monitor.'
            except CalendarError as error:
                title, text = 'Não foi possível conectar', str(error)
                with Session(engine) as db:
                    _put(db, 'google_error', str(error))
                    db.commit()
            body = PAGE.format(title=title, text=text).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.server.done = True

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.done = False
    server.timeout = 1
    redirect = f'http://127.0.0.1:{server.server_address[1]}'
    _pending['server'] = server

    def serve():
        deadline = time.monotonic() + wait
        try:
            while not server.done and time.monotonic() < deadline:
                server.handle_request()
        except (OSError, ValueError):
            pass  # servidor fechado por uma nova tentativa
        finally:
            server.server_close()
            if _pending.get('server') is server:
                _pending.pop('server', None)

    threading.Thread(target=serve, daemon=True).start()
    url = AUTH_URL + '?' + urlencode({
        'client_id': client_id, 'redirect_uri': redirect, 'response_type': 'code', 'scope': SCOPES,
        'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
        'access_type': 'offline', 'prompt': 'consent'})
    with Session(engine) as db:
        _put(db, 'google_error', '')
        db.commit()
    if opener:
        opener(url)
    return url


def _finish(engine, vault, client_id, client_secret, code, verifier, redirect) -> None:
    try:
        with _client() as client:
            response = client.post(TOKEN_URL, data={
                'client_id': client_id, 'client_secret': client_secret, 'code': code,
                'code_verifier': verifier, 'grant_type': 'authorization_code', 'redirect_uri': redirect})
            if response.status_code != 200 or not response.json().get('refresh_token'):
                raise CalendarError('O Google recusou a autorização. Confira o ID e a chave do cliente.')
            tokens = response.json()
            if 'calendar.events' not in tokens.get('scope', ''):
                raise CalendarError('A permissão de agenda não foi concedida. Conecte de novo e marque a caixa da agenda.')
            profile = client.get(USERINFO_URL, headers={'Authorization': f'Bearer {tokens["access_token"]}'})
            email = profile.json().get('email', '') if profile.status_code == 200 else ''
    except (httpx.HTTPError, ValueError):
        raise CalendarError('Sem conexão com o Google. Tente novamente.') from None
    vault.set(TOKEN_REF, tokens['refresh_token'])
    _access.update(token=tokens['access_token'], expires=time.monotonic() + int(tokens.get('expires_in', 3600)) - 60)
    with Session(engine) as db:
        _put(db, 'google_email', email)
        _put(db, 'google_error', '')
        db.commit()


def _token(engine, vault, client: httpx.Client) -> str:
    if _access.get('token') and _access.get('expires', 0) > time.monotonic():
        return _access['token']
    with Session(engine) as db:
        client_id = _get(db, 'google_client_id')
    response = client.post(TOKEN_URL, data={
        'client_id': client_id, 'client_secret': vault.get(SECRET_REF) or '',
        'refresh_token': vault.get(TOKEN_REF) or '', 'grant_type': 'refresh_token'})
    if response.status_code in (400, 401):
        vault.delete(TOKEN_REF)
        _access.clear()
        raise CalendarError('O acesso à agenda expirou ou foi revogado. Conecte a conta novamente.')
    response.raise_for_status()
    tokens = response.json()
    _access.update(token=tokens['access_token'], expires=time.monotonic() + int(tokens.get('expires_in', 3600)) - 60)
    return _access['token']


# ---- Sincronização --------------------------------------------------------

def event_for(demand: Demand, fronts: dict[int, str]) -> dict | None:
    """Evento de dia inteiro na data de retorno (etapa Acompanhar) ou no prazo. Sem data, sem evento."""
    if demand.stage in ('ganho', 'perdido'):
        return None
    returning = demand.stage == 'acompanhar' and demand.return_date
    day = demand.return_date if returning else demand.due or demand.return_date
    if not day:
        return None
    front = fronts.get(demand.front_id, f'Frente {demand.front_id}')
    details = [f'Etapa: {STAGES.get(demand.stage, demand.stage)}']
    if demand.next_action:
        details.append(f'Próxima ação: {demand.next_action}')
    details.append('Evento criado pelo Monitor. Alterações feitas aqui são substituídas quando a demanda muda.')
    prefix = 'Retorno: ' if returning or not demand.due else ''
    return {
        'summary': f'{prefix}{demand.title} · {front}',
        'description': '\n'.join(details),
        'start': {'date': day.isoformat()},
        'end': {'date': (day + timedelta(days=1)).isoformat()},
        'transparency': 'transparent',
        'extendedProperties': {'private': {'monitor_demand': str(demand.id)}},
    }


def _fingerprint(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def reminder_event_for(reminder, link, zone):
    start = as_utc(reminder.when)
    return {'summary': reminder.text, 'description': 'Compromisso criado pelo assistente do Monitor a pedido do usuário.',
            'start': {'dateTime': start.isoformat(), 'timeZone': zone},
            'end': {'dateTime': (start + timedelta(minutes=link.duration_minutes)).isoformat(), 'timeZone': zone},
            'extendedProperties': {'private': {'monitor_reminder': str(reminder.id)}}}


def sync_reminders(db, client, headers, result, identifier=None):
    """Somente os lembretes cujo envio ao Google foi pedido explicitamente."""
    from .reminders import settings
    zone = settings(db)['timezone']
    query = select(ReminderCalendarLink)
    if identifier is not None:
        query = query.where(ReminderCalendarLink.reminder_id == identifier)
    for link in db.exec(query).all():
        reminder = db.get(Reminder, link.reminder_id)
        if not reminder or reminder.status == 'cancelado':
            if link.fingerprint:
                response = client.delete(f'{EVENTS_URL}/{link.event_id}', headers=headers)
                if response.status_code not in (200, 204, 404, 410):
                    response.raise_for_status()
                result['removed'] += 1
            db.delete(link)
            db.commit()
            continue
        body = reminder_event_for(reminder, link, zone)
        mark = _fingerprint(body)
        if link.fingerprint == mark:
            continue
        created = not link.fingerprint
        response = (client.post(EVENTS_URL, headers=headers, json={**body, 'id': link.event_id}) if created
                    else client.put(f'{EVENTS_URL}/{link.event_id}', headers=headers, json=body))
        if created and response.status_code == 409:
            response = client.put(f'{EVENTS_URL}/{link.event_id}', headers=headers, json=body)
        elif not created and response.status_code in (404, 410):
            link.event_id, link.fingerprint = uuid.uuid4().hex, ''
            db.add(link)
            db.commit()
            response = client.post(EVENTS_URL, headers=headers, json={**body, 'id': link.event_id})
            created = True
        response.raise_for_status()
        link.fingerprint, link.synced_at = mark, now()
        db.add(link)
        db.commit()
        result['created' if created else 'updated'] += 1


def sync(engine, vault, *, reminder_id=None) -> dict:
    """Leva o estado das demandas para a agenda. Seguro para repetir: falhas ficam para a próxima rodada."""
    result = {'created': 0, 'updated': 0, 'removed': 0}
    if not vault.get(TOKEN_REF) or not _lock.acquire(blocking=False):
        return result
    error = ''
    try:
        with Session(engine) as db, _client() as client:
            headers = {'Authorization': f'Bearer {_token(engine, vault, client)}'}
            fronts = prefs.front_names(db)
            desired = {d.id: body for d in db.exec(select(Demand)).all() if (body := event_for(d, fronts))} if reminder_id is None else {}
            links = {link.demand_id: link for link in db.exec(select(CalendarLink)).all()} if reminder_id is None else {}
            for demand_id, body in desired.items():
                mark = _fingerprint(body)
                link = links.get(demand_id)
                if link and link.fingerprint == mark:
                    continue
                if not link:
                    # O identificador é gravado antes do envio: repetir após uma queda não duplica o evento.
                    link = CalendarLink(demand_id=demand_id, event_id=uuid.uuid4().hex)
                    db.add(link)
                    db.commit()
                created = not link.fingerprint
                response = (client.post(EVENTS_URL, headers=headers, json={**body, 'id': link.event_id}) if created
                            else client.put(f'{EVENTS_URL}/{link.event_id}', headers=headers, json=body))
                if created and response.status_code == 409:
                    response = client.put(f'{EVENTS_URL}/{link.event_id}', headers=headers, json=body)
                elif not created and response.status_code in (404, 410):
                    link.event_id = uuid.uuid4().hex  # evento apagado na agenda: recria
                    link.fingerprint = ''
                    db.add(link)
                    db.commit()
                    response = client.post(EVENTS_URL, headers=headers, json={**body, 'id': link.event_id})
                    created = True
                response.raise_for_status()
                link.fingerprint = mark
                link.synced_at = now()
                db.add(link)
                db.commit()
                result['created' if created else 'updated'] += 1
            for demand_id, link in links.items():
                if demand_id in desired:
                    continue
                if link.fingerprint:
                    response = client.delete(f'{EVENTS_URL}/{link.event_id}', headers=headers)
                    if response.status_code not in (200, 204, 404, 410):
                        response.raise_for_status()
                    result['removed'] += 1
                db.delete(link)
                db.commit()
            sync_reminders(db, client, headers, result, reminder_id)
    except CalendarError as failure:
        error = str(failure)
    except httpx.HTTPStatusError as failure:
        code = failure.response.status_code
        error = ('O Google recusou o acesso à agenda. Verifique se a API Google Calendar está ativada no projeto.'
                 if code == 403 else f'O Google Agenda respondeu com erro {code}. Nova tentativa em instantes.')
    except (httpx.HTTPError, ValueError):
        error = 'Sem conexão com o Google Agenda. Nova tentativa em instantes.'
    finally:
        _lock.release()
    with Session(engine) as db:
        _put(db, 'google_error', error)
        if not error:
            _put(db, 'google_last_sync', now().isoformat())
        db.commit()
    return {**result, 'error': error}
