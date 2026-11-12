"""Checagens locais: resultados observados, sem inferir disponibilidade durante pausas."""
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select, delete

from .models import Notice, Site, SiteCheck, SiteIncident, as_utc, now

_lock = threading.Lock()
SUGGESTIONS = [
    ('Rocha Comercial', 'https://rochacomercial.com.br', 1),
    ('Carteira Pronta', 'https://www.carteirapronta.com.br', 2),
    ('WebQ', 'https://www.webq.com.br', 3),
    ('Nextlink', 'http://www.nextlink.com.br', 4),
]


class SiteInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=1000)
    front_id: int = Field(ge=1, le=4)
    expected_text: str = Field(default='', max_length=500)
    enabled: bool = True

    @field_validator('url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip()
        try:
            parts = urlsplit(value)
            if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.fragment:
                raise ValueError()
            parts.port
            httpx.URL(value)
            if any(char.isspace() for char in value):
                raise ValueError()
        except (ValueError, httpx.InvalidURL):
            raise ValueError('Use uma URL HTTP ou HTTPS sem senha ou fragmento.')
        return value

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError('Informe o nome do site.')
        return value.strip()


def certificate_expiry(url):
    parts = urlsplit(url)
    if parts.scheme != 'https':
        return None
    context = ssl.create_default_context()
    with socket.create_connection((parts.hostname, parts.port or 443), timeout=5) as sock:
        with context.wrap_socket(sock, server_hostname=parts.hostname) as secured:
            certificate = secured.getpeercert()
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate['notAfter']), timezone.utc)


def probe(site, *, transport=None, certificate=certificate_expiry):
    result = dict(ok=False, status_code=None, latency_ms=None, detail='', ssl_expires=None)
    started = time.monotonic()
    final_url = site.url
    try:
        with httpx.Client(timeout=12, follow_redirects=True, max_redirects=5, trust_env=False,
                          transport=transport, headers={'User-Agent': 'Monitor/0.4 site-check'}) as client:
            with client.stream('GET', site.url) as response:
                result['status_code'] = response.status_code
                final_url = str(response.url)
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 2_000_000 or time.monotonic() - started > 20:
                        result['detail'] = 'Resposta excedeu o limite de tamanho ou tempo.'
                        break
                else:
                    text = bytes(content).decode(response.encoding or 'utf-8', errors='replace')
                    result['ok'] = 200 <= response.status_code < 300 and (not site.expected_text or site.expected_text.casefold() in text.casefold())
                    result['detail'] = ('Resposta válida.' if result['ok'] else
                                        'Texto esperado não encontrado.' if 200 <= response.status_code < 300 else f'HTTP {response.status_code}.')
                result['latency_ms'] = round((time.monotonic() - started) * 1000)
    except httpx.TimeoutException:
        result['detail'] = 'Tempo de resposta esgotado.'
    except (httpx.HTTPError, httpx.InvalidURL) as error:
        result['detail'] = 'Falha de conexão, redirecionamento ou certificado TLS.'
        cause = error
        for _ in range(10):
            if isinstance(cause, socket.gaierror):
                result['detail'] = 'Endereço não localizado no DNS.'
                break
            if isinstance(cause, ssl.SSLCertVerificationError):
                result['detail'] = 'O certificado TLS não passou na verificação.'
                break
            cause = cause.__cause__ or cause.__context__
            if cause is None:
                break
    if result['status_code'] is not None and urlsplit(final_url).scheme == 'https':
        try:
            result['ssl_expires'] = certificate(final_url)
        except (OSError, ValueError, KeyError):
            result['detail'] += ' Validade do certificado indisponível.'
    return result


def check_all(engine, identifier=None, *, transport=None, certificate=certificate_expiry):
    # Uma rodada por vez: evita incidentes duplicados entre botão e agendador.
    if not _lock.acquire(blocking=False):
        return False
    try:
        with Session(engine) as db:
            sites = db.exec(select(Site).where(Site.enabled == True)).all()
            sites = [site for site in sites if identifier is None or site.id == identifier]
        for site in sites:
            result = probe(site, transport=transport, certificate=certificate)
            instant = now()
            with Session(engine) as db:
                current = db.get(Site, site.id)
                # Configuração mudou durante a requisição: descartar resultado antigo.
                if not current or not current.enabled or current.url != site.url or current.expected_text != site.expected_text:
                    continue
                check = SiteCheck(site_id=site.id, checked_at=instant, **result)
                db.add(check)
                incident = db.exec(select(SiteIncident).where(SiteIncident.site_id == site.id, SiteIncident.closed_at == None)).first()
                if not result['ok'] and not incident:
                    incident = SiteIncident(site_id=site.id, opened_at=instant, detail=result['detail'])
                    db.add(incident)
                    db.flush()
                    db.add(Notice(key=f'site:down:{incident.id}', kind='site', title=f'Falha em {site.name}', body=result['detail']))
                elif result['ok'] and incident:
                    incident.closed_at = instant
                    db.add(incident)
                    db.add(Notice(key=f'site:up:{incident.id}', kind='site', title=f'{site.name} voltou a responder', body='Checagem local concluída com sucesso.'))
                expiry = result['ssl_expires']
                if expiry and expiry < instant + timedelta(days=14):
                    key = f'site:ssl:{site.id}:{expiry.date()}'
                    if not db.exec(select(Notice).where(Notice.key == key)).first():
                        db.add(Notice(key=key, kind='site', title=f'Certificado de {site.name} perto do vencimento', body=f'Validade até {expiry.date().isoformat()}.'))
                db.exec(delete(SiteCheck).where(SiteCheck.checked_at < instant - timedelta(days=35)))
                db.commit()
        return True
    finally:
        _lock.release()


def snapshot(db, site):
    checks = db.exec(select(SiteCheck).where(SiteCheck.site_id == site.id, SiteCheck.checked_at >= now() - timedelta(days=30)).order_by(SiteCheck.id.desc())).all()
    latest = checks[0] if checks else None
    latencies = [c.latency_ms for c in checks if c.latency_ms is not None]
    return {**site.model_dump(), 'created_at': as_utc(site.created_at),
            'latest': ({**latest.model_dump(), 'checked_at': as_utc(latest.checked_at), 'ssl_expires': as_utc(latest.ssl_expires)} if latest else None),
            'samples': len(checks), 'success_percent': round(100 * sum(c.ok for c in checks) / len(checks), 2) if checks else None,
            'average_ms': round(sum(latencies) / len(latencies)) if latencies else None,
            'observed_since': as_utc(checks[-1].checked_at) if checks else None}


def router(engine, session, demo):
    routes = APIRouter()

    def writable():
        if demo:
            raise HTTPException(409, 'Saia da demonstração para monitorar sites reais.')

    @routes.get('/sites/suggestions')
    def suggestions():
        return [dict(name=name, url=url, front_id=front) for name, url, front in SUGGESTIONS]

    @routes.get('/sites')
    def listing(db: Session = Depends(session)):
        return [snapshot(db, site) for site in db.exec(select(Site).order_by(Site.id)).all()]

    @routes.post('/sites', status_code=201)
    def create(payload: SiteInput, db: Session = Depends(session)):
        writable()
        if len(db.exec(select(Site)).all()) >= 50:
            raise HTTPException(409, 'Limite de 50 sites atingido.')
        item = Site(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return snapshot(db, item)

    @routes.put('/sites/{identifier}')
    def update(identifier: int, payload: SiteInput, db: Session = Depends(session)):
        writable()
        item = db.get(Site, identifier)
        if not item:
            raise HTTPException(404, 'Site não encontrado.')
        if item.url != payload.url or item.expected_text != payload.expected_text:
            # Uma URL/regra diferente inicia outra série; preserva incidentes anteriores.
            db.exec(delete(SiteCheck).where(SiteCheck.site_id == identifier))
            for incident in db.exec(select(SiteIncident).where(SiteIncident.site_id == identifier, SiteIncident.closed_at == None)).all():
                incident.closed_at = now()
                db.add(incident)
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        db.add(item)
        db.commit()
        return snapshot(db, item)

    @routes.delete('/sites/{identifier}', status_code=204)
    def remove(identifier: int, db: Session = Depends(session)):
        writable()
        item = db.get(Site, identifier)
        if not item:
            raise HTTPException(404, 'Site não encontrado.')
        db.exec(delete(SiteCheck).where(SiteCheck.site_id == identifier))
        db.exec(delete(SiteIncident).where(SiteIncident.site_id == identifier))
        db.delete(item)
        db.commit()

    @routes.post('/sites/{identifier}/check')
    def check(identifier: int, db: Session = Depends(session)):
        writable()
        item = db.get(Site, identifier)
        if not item or not item.enabled:
            raise HTTPException(409, 'Site inexistente ou pausado.')
        if not check_all(engine, identifier):
            raise HTTPException(409, 'Uma checagem já está em andamento.')
        db.expire_all()
        return snapshot(db, db.get(Site, identifier))

    @routes.get('/sites/{identifier}/history')
    def history(identifier: int, db: Session = Depends(session)):
        if not db.get(Site, identifier):
            raise HTTPException(404, 'Site não encontrado.')
        checks = db.exec(select(SiteCheck).where(SiteCheck.site_id == identifier).order_by(SiteCheck.id.desc()).limit(100)).all()
        incidents = db.exec(select(SiteIncident).where(SiteIncident.site_id == identifier).order_by(SiteIncident.id.desc()).limit(50)).all()
        return {'checks': [{**c.model_dump(), 'checked_at': as_utc(c.checked_at), 'ssl_expires': as_utc(c.ssl_expires)} for c in checks],
                'incidents': [{**i.model_dump(), 'opened_at': as_utc(i.opened_at), 'closed_at': as_utc(i.closed_at)} for i in incidents]}

    return routes
