"""Perfis do Instagram pela API oficial (somente leitura).

O token de acesso de cada perfil fica no Gerenciador de Credenciais do Windows.
Seguidores e total de posts são guardados uma vez por dia para calcular a variação da semana.
"""
import base64
import threading
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .models import SocialMedia, SocialProfile, SocialSnapshot, as_utc, now
from .secrets_store import SecretError

API = 'https://graph.instagram.com'
PROFILE_FIELDS = 'user_id,username,name,profile_picture_url,followers_count,media_count'
MEDIA_FIELDS = 'id,media_product_type,timestamp,like_count,comments_count'
TRANSPORT = None  # substituído nos testes
AVATAR_LIMIT = 400_000
_lock = threading.Lock()


class SocialError(Exception):
    pass


class ProfileInput(BaseModel):
    front_id: int = Field(ge=1, le=4)
    token: str = Field(min_length=20, max_length=600, pattern=r'^[A-Za-z0-9_\-.|]+$')


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(20, connect=5), transport=TRANSPORT)


def _call(client: httpx.Client, path: str, token: str, **params) -> dict:
    try:
        response = client.get(f'{API}{path}', params={**params, 'access_token': token})
    except httpx.HTTPError:
        raise SocialError('Sem conexão com o Instagram. Nova tentativa em instantes.') from None
    if response.status_code in (400, 401, 403):
        try:
            code = response.json().get('error', {}).get('code')
        except ValueError:
            code = None
        if code == 190 or response.status_code == 401:
            raise SocialError('O token expirou ou foi revogado. Gere um novo token e conecte o perfil de novo.')
        raise SocialError('O Instagram recusou a consulta. Confira se a conta é profissional e se o token tem a permissão básica.')
    if response.status_code != 200:
        raise SocialError(f'O Instagram respondeu com erro {response.status_code}. Nova tentativa em instantes.')
    try:
        return response.json()
    except ValueError:
        raise SocialError('O Instagram devolveu uma resposta inesperada.') from None


def _avatar(client: httpx.Client, url: str | None) -> str:
    """Baixa a foto do perfil e devolve como data URI; o endereço original expira em poucas horas."""
    if not url or not url.startswith('https://'):
        return ''
    try:
        response = client.get(url)
        kind = response.headers.get('content-type', '').split(';')[0]
        if response.status_code == 200 and kind in ('image/jpeg', 'image/png', 'image/webp') and len(response.content) <= AVATAR_LIMIT:
            return f'data:{kind};base64,{base64.b64encode(response.content).decode()}'
    except httpx.HTTPError:
        pass
    return ''


def _parse(value: str) -> datetime | None:
    try:
        return as_utc(datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z'))
    except (TypeError, ValueError):
        return None


def _collect(db: Session, client: httpx.Client, profile: SocialProfile, token: str, today: date) -> None:
    me = _call(client, '/me', token, fields=PROFILE_FIELDS)
    profile.username = str(me.get('username') or profile.username)
    profile.name = str(me.get('name') or '')[:120]
    profile.avatar = _avatar(client, me.get('profile_picture_url')) or profile.avatar
    snapshot = db.exec(select(SocialSnapshot).where(SocialSnapshot.profile_id == profile.id, SocialSnapshot.day == today)).first()
    snapshot = snapshot or SocialSnapshot(profile_id=profile.id, day=today)
    snapshot.followers, snapshot.media_count = int(me.get('followers_count') or 0), int(me.get('media_count') or 0)
    db.add(snapshot)

    known = {item.media_id: item for item in db.exec(select(SocialMedia).where(SocialMedia.profile_id == profile.id)).all()}

    def remember(item: dict, kind: str):
        published = _parse(item.get('timestamp'))
        if not item.get('id') or not published:
            return
        row = known.get(str(item['id'])) or SocialMedia(profile_id=profile.id, media_id=str(item['id']), kind=kind, published_at=published)
        row.likes, row.comments = int(item.get('like_count') or 0), int(item.get('comments_count') or 0)
        db.add(row)

    for item in _call(client, '/me/media', token, fields=MEDIA_FIELDS, limit=50).get('data', []):
        remember(item, 'post')
    try:
        # Stories somem em 24 h: cada coleta registra os que estão no ar para contar a semana.
        for item in _call(client, '/me/stories', token, fields='id,timestamp').get('data', []):
            remember(item, 'story')
        profile.stories_ok = True
    except SocialError:
        profile.stories_ok = False
    cutoff = now() - timedelta(days=60)
    for row in known.values():
        if as_utc(row.published_at) < cutoff:
            db.delete(row)


def _refresh_token(client: httpx.Client, profile: SocialProfile, token: str, vault) -> str:
    """Tokens de longa duração valem 60 dias; renova a cada 30."""
    if profile.token_at and now() - as_utc(profile.token_at) < timedelta(days=30):
        return token
    try:
        fresh = _call(client, '/refresh_access_token', token, grant_type='ig_refresh_token').get('access_token')
    except SocialError:
        return token
    if fresh:
        vault.set(profile.keyring_ref, fresh)
        profile.token_at = now()
        return fresh
    return token


def sync(engine, vault, identifier: int | None = None, today: date | None = None) -> None:
    if not _lock.acquire(blocking=False):
        return
    try:
        with Session(engine) as db, _client() as client:
            query = select(SocialProfile) if identifier is None else select(SocialProfile).where(SocialProfile.id == identifier)
            for profile in db.exec(query).all():
                token = vault.get(profile.keyring_ref)
                try:
                    if not token:
                        raise SocialError('Token não encontrado neste computador. Conecte o perfil de novo.')
                    token = _refresh_token(client, profile, token, vault)
                    _collect(db, client, profile, token, today or date.today())
                    profile.status, profile.status_detail, profile.last_sync = 'ok', '', now()
                except SocialError as error:
                    db.rollback()
                    profile = db.get(SocialProfile, profile.id)
                    profile.status, profile.status_detail = 'erro', str(error)
                db.add(profile)
                db.commit()
    finally:
        _lock.release()


def output(db: Session, profile: SocialProfile, instant: datetime | None = None) -> dict:
    instant = instant or now()
    snapshots = db.exec(select(SocialSnapshot).where(SocialSnapshot.profile_id == profile.id).order_by(SocialSnapshot.day)).all()
    latest = snapshots[-1] if snapshots else None
    week_ago = instant.date() - timedelta(days=7)
    # Referência: a coleta mais recente com 7 dias ou mais; sem ela, a mais antiga disponível.
    older = [s for s in snapshots if s.day <= week_ago]
    base = older[-1] if older else snapshots[0] if len(snapshots) > 1 else None
    since = instant - timedelta(days=7)
    recent = [m for m in db.exec(select(SocialMedia).where(SocialMedia.profile_id == profile.id)).all() if as_utc(m.published_at) >= since]
    posts = [m for m in recent if m.kind == 'post']
    return {
        'id': profile.id, 'front_id': profile.front_id, 'network': profile.network, 'username': profile.username,
        'name': profile.name, 'avatar': profile.avatar, 'status': profile.status, 'status_detail': profile.status_detail,
        'last_sync': as_utc(profile.last_sync),
        'followers': latest.followers if latest else None,
        'posts': latest.media_count if latest else None,
        'followers_change': latest.followers - base.followers if latest and base else None,
        'change_days': min(7, (latest.day - base.day).days) if latest and base else 0,
        'posts_week': len(posts),
        'stories_week': len([m for m in recent if m.kind == 'story']) if profile.stories_ok else None,
        'likes_week': sum(m.likes for m in posts),
        'comments_week': sum(m.comments for m in posts),
    }


def router(engine, session, vault, demo):
    api = APIRouter()

    def writable():
        if demo:
            raise HTTPException(409, 'Perfis reais ficam indisponíveis no modo de demonstração.')

    @api.get('/social')
    def listing(db: Session = Depends(session)):
        return [output(db, profile) for profile in db.exec(select(SocialProfile).order_by(SocialProfile.front_id, SocialProfile.id)).all()]

    @api.post('/social', status_code=201)
    def connect(payload: ProfileInput, db: Session = Depends(session)):
        writable()
        try:
            with _client() as client:
                me = _call(client, '/me', payload.token, fields='user_id,username')
        except SocialError as error:
            raise HTTPException(400, str(error)) from None
        account = str(me.get('user_id') or me.get('id') or '')
        if not account or not me.get('username'):
            raise HTTPException(400, 'O Instagram não devolveu os dados da conta. Confira o token.')
        if db.exec(select(SocialProfile).where(SocialProfile.account_id == account)).first():
            raise HTTPException(409, 'Este perfil já está conectado.')
        reference = f'instagram:{account}'
        try:
            vault.set(reference, payload.token)
        except SecretError as error:
            raise HTTPException(500, str(error)) from None
        profile = SocialProfile(front_id=payload.front_id, account_id=account, username=str(me['username']), keyring_ref=reference, token_at=now())
        db.add(profile)
        db.commit()
        db.refresh(profile)
        sync(engine, vault, profile.id)
        db.refresh(profile)
        return output(db, profile)

    @api.post('/social/{identifier}/sync')
    def refresh(identifier: int, db: Session = Depends(session)):
        writable()
        if not db.get(SocialProfile, identifier):
            raise HTTPException(404, 'Perfil não encontrado.')
        sync(engine, vault, identifier)
        db.expire_all()
        return output(db, db.get(SocialProfile, identifier))

    @api.delete('/social/{identifier}', status_code=204)
    def remove(identifier: int, db: Session = Depends(session)):
        writable()
        profile = db.get(SocialProfile, identifier)
        if not profile:
            raise HTTPException(404, 'Perfil não encontrado.')
        for table in (SocialSnapshot, SocialMedia):
            for row in db.exec(select(table).where(table.profile_id == identifier)).all():
                db.delete(row)
        vault.delete(profile.keyring_ref)
        db.delete(profile)
        db.commit()

    return api
