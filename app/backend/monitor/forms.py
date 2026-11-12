"""Coleta autenticada do relay: confirmar somente depois do commit local."""
import hashlib
import threading
from email.utils import parseaddr
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlmodel import Session, select

from .inbox import setting
from .models import Demand, Email, Event, FormEntry, Notice, Setting, Site, as_utc, now
from .secrets_store import SecretError

_lock = threading.Lock()


def same_submission(email, entry):
    # Fallback conservador: não usa o resumo da IA nem apenas o remetente.
    normalize = lambda value: ' '.join(value.casefold().split())
    return (email.date is not None and
            abs((as_utc(email.date) - as_utc(entry.received_at)).total_seconds()) <= 600 and
            parseaddr(email.sender)[1].casefold() == entry.email.casefold() and
            normalize(email.body_text) == normalize(entry.message))


def demand_for_email(db, email, front_id):
    if not email:
        return None
    for entry in db.exec(select(FormEntry).where(FormEntry.front_id == front_id, FormEntry.demand_id != None)).all():
        if same_submission(email, entry):
            demand = db.get(Demand, entry.demand_id)
            if demand:
                return demand
    return None


def demand_for_form(db, entry):
    for demand in db.exec(select(Demand).where(Demand.front_id == entry.front_id, Demand.channel == 'email')).all():
        if demand.origin_ref.startswith('email:'):
            email = db.get(Email, int(demand.origin_ref.split(':')[1]))
            if email and same_submission(email, entry):
                return demand
    return None


class RelayConfig(BaseModel):
    url: str = Field(max_length=1000)
    token: str | None = Field(default=None, min_length=32, max_length=500)

    @field_validator('url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        if not value:
            return value
        try:
            parts = urlsplit(value)
            if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError()
            if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost')):
                raise ValueError()
            parts.port
            httpx.URL(value)
        except (ValueError, httpx.InvalidURL):
            raise ValueError('O relay precisa de HTTPS (HTTP permitido só em localhost).')
        return value


class RelayEvent(BaseModel):
    id: int = Field(gt=0)
    site_id: int = Field(gt=0)
    received_at: datetime
    name: str = Field(max_length=200)
    email: str = Field(min_length=3, max_length=200, pattern=r'^[^@\s]+@[^@\s]+$')
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10000)


def config(db, vault):
    return {'url': setting(db, 'relay:url', ''), 'has_token': bool(vault.get('relay:token')),
            'last_sync': setting(db, 'relay:last_sync', ''), 'status': setting(db, 'relay:status', 'Não configurado')}


def sync(engine, vault, *, transport=None):
    if not _lock.acquire(blocking=False):
        return False
    try:
        with Session(engine) as db:
            url = setting(db, 'relay:url', '')
        token = vault.get('relay:token')
        if not url or not token:
            return False
        try:
            with httpx.Client(timeout=15, trust_env=False, transport=transport, follow_redirects=False,
                              headers={'Authorization': f'Bearer {token}'}) as client:
                # after=0 devolve só os não confirmados; um ACK perdido é seguro.
                with client.stream('GET', f'{url}/events?after=0') as response:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 8_000_000:
                            raise ValueError('response size')
                from pydantic import TypeAdapter
                entries = TypeAdapter(list[RelayEvent]).validate_json(bytes(content))
                if len(entries) > 100:
                    raise ValueError('batch size')
                source = hashlib.sha256(url.encode()).hexdigest()[:24]
                identifiers = []
                with Session(engine) as db:
                    db.execute(text('BEGIN IMMEDIATE'))
                    for entry in entries:
                        site = db.get(Site, entry.site_id)
                        if not site:
                            raise ValueError('site mapping')
                        key = f'{source}:{entry.id}'
                        existing = db.exec(select(FormEntry).where(FormEntry.source_key == key)).first()
                        if not existing:
                            record = FormEntry(source_key=key, front_id=site.front_id,
                                               **entry.model_dump(exclude={'id'}))
                            db.add(record)
                            db.flush()
                            db.add(Notice(key=f'form:{record.id}', kind='formulario', title=f'Novo contato em {site.name}',
                                          body='Revise o formulário na tela Sites para criar uma demanda.'))
                        identifiers.append(entry.id)
                    db.commit()
                if identifiers:
                    ack = client.post(f'{url}/events/ack', json={'ids': identifiers})
                    ack.raise_for_status()
            status = 'Conectado'
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            status = 'Falha ao coletar ou confirmar. Confira URL, token e IDs dos sites; os envios serão tentados novamente.'
        with Session(engine) as db:
            db.merge(Setting(key='relay:status', value=status))
            if status == 'Conectado':
                db.merge(Setting(key='relay:last_sync', value=now().isoformat()))
            db.commit()
        return status == 'Conectado'
    finally:
        _lock.release()


def router(engine, session, vault, demo):
    routes = APIRouter()

    def writable():
        if demo:
            raise HTTPException(409, 'Saia da demonstração para conectar formulários reais.')

    @routes.get('/relay')
    def get_config(db: Session = Depends(session)):
        return config(db, vault)

    @routes.put('/relay')
    def configure(payload: RelayConfig, db: Session = Depends(session)):
        writable()
        with _lock:
            if not payload.url:
                vault.delete('relay:token')
            elif payload.token:
                try:
                    vault.set('relay:token', payload.token)
                except SecretError as error:
                    raise HTTPException(503, str(error)) from None
            elif payload.url != setting(db, 'relay:url', '') or not vault.get('relay:token'):
                raise HTTPException(422, 'Informe o token do aplicativo para este relay.')
            db.merge(Setting(key='relay:url', value=payload.url))
            db.merge(Setting(key='relay:status', value='Aguardando coleta' if payload.url else 'Não configurado'))
            db.merge(Setting(key='relay:last_sync', value=''))
            db.commit()
        return config(db, vault)

    @routes.post('/relay/sync')
    def collect():
        writable()
        if not sync(engine, vault):
            raise HTTPException(409, 'Coleta indisponível. Confira a configuração ou aguarde a rodada em andamento.')
        return {'ok': True}

    @routes.get('/forms')
    def listing(db: Session = Depends(session)):
        records = db.exec(select(FormEntry).order_by((FormEntry.status == 'pendente').desc(), FormEntry.id.desc()).limit(200)).all()
        return [{**record.model_dump(), 'received_at': as_utc(record.received_at)} for record in records]

    @routes.post('/forms/{identifier}/{action}')
    def resolve(identifier: int, action: str, db: Session = Depends(session)):
        writable()
        if action not in ('accept', 'dismiss'):
            raise HTTPException(404, 'Ação inválida.')
        db.execute(text('BEGIN IMMEDIATE'))
        entry = db.get(FormEntry, identifier)
        if not entry:
            raise HTTPException(404, 'Formulário não encontrado.')
        if entry.status != 'pendente':
            return {'demand_id': entry.demand_id, 'status': entry.status}
        if action == 'accept':
            demand = demand_for_form(db, entry)
            duplicate = demand is not None
            if not demand:
                demand = Demand(title=entry.subject, front_id=entry.front_id, contact=entry.email, channel='formulario',
                            summary=entry.message[:6000], origin_ref=f'form:{entry.id}', created_by='usuario')
                db.add(demand)
                db.flush()
            db.add(Event(demand_id=demand.id, description='Formulário vinculado à demanda de e-mail existente.' if duplicate else 'Demanda criada pelo usuário a partir de um formulário.'))
            entry.demand_id = demand.id
            entry.status = 'duplicada' if duplicate else 'aceita'
        else:
            entry.status = 'descartada'
        db.add(entry)
        notice = db.exec(select(Notice).where(Notice.key == f'form:{entry.id}')).first()
        if notice:
            notice.read, notice.desktop_status = True, 'silenciada'
            db.add(notice)
        db.commit()
        return {'demand_id': entry.demand_id, 'status': entry.status}

    return routes
