"""Perfis do Instagram pela API oficial (somente leitura).

O token de acesso de cada perfil fica no Gerenciador de Credenciais do Windows.
Seguidores e total de posts são guardados uma vez por dia para calcular a variação da semana.
"""
import base64
import re
import threading
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from sqlalchemy import text

from .models import SocialComment, SocialMedia, SocialProfile, SocialSnapshot, Demand, Event, Notice, as_utc, now
from . import social_browser
from .deadlines import fold
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


class BrowserProfileInput(BaseModel):
    account_id: int = Field(gt=0)
    front_id: int = Field(ge=1, le=4)
    auto_demands: bool = True


class BrowserSettings(BaseModel):
    enabled: bool
    auto_demands: bool


def commercial_request(content):
    value = ' '.join(fold(content).split())
    patterns = (r'\b(quero|preciso|gostaria|solicito|pode[m]?|envi[ae]|mande)\b.{0,65}\b(orcamento|cotacao|proposta|contratar)\b',
                r'\b(qual|quais)\b.{0,25}\b(valor|preco|precos|valores)\b', r'\bquanto custa\b',
                r'\bcomo (?:posso |faco para )?(contratar|comprar|adquirir)\b',
                r'\b(nao recebi|pedido atrasado|produto com defeito|preciso de suporte)\b')
    return any(re.search(pattern, value) for pattern in patterns)


def create_comment_demand(db, comment, profile, automatic=False):
    origin = f'instagram:{comment.comment_id}'
    demand = db.get(Demand, comment.demand_id) if comment.demand_id else None
    demand = demand or db.exec(select(Demand).where(Demand.origin_ref == origin)).first()
    if not demand:
        demand = Demand(title=f'Responder @{comment.author}: {comment.text}'[:200], front_id=profile.front_id,
                        contact=f'@{comment.author}', channel='instagram', origin_ref=origin,
                        summary=f'Comentário em @{profile.username}:\n{comment.text}\n\nFonte: {comment.post_url}'[:6000],
                        next_action='Conferir o comentário e responder ao contato no Instagram.',
                        created_by='automacao' if automatic else 'usuario')
        db.add(demand)
        db.flush()
        db.add(Event(demand_id=demand.id, description='Demanda criada de comentário do Instagram por ' + ('regra comercial automática.' if automatic else 'confirmação do usuário.')))
        if not db.exec(select(Notice).where(Notice.key == origin)).first():
            db.add(Notice(key=origin, kind='instagram', title=f'Comentário de @{comment.author}',
                          body='Novo pedido comercial recebido pelo Instagram.', demand_id=demand.id))
    comment.demand_id, comment.status = demand.id, 'demanda'
    db.add(comment)
    return demand


def _browser_sync(engine, identifier):
    with Session(engine) as db:
        profile = db.get(SocialProfile, identifier)
        if not profile or not profile.enabled:
            return
        path, username, connected_at = profile.browser_path, profile.username, as_utc(profile.browser_since)
    try:
        result = social_browser.collect(path, username)
        with Session(engine) as db:
            db.execute(text('BEGIN IMMEDIATE'))
            profile = db.get(SocialProfile, identifier)
            if (not profile or not profile.enabled or profile.browser_path != path or profile.username != username
                    or as_utc(profile.browser_since) != connected_at):
                return
            profile.name = result['name']
            today = date.today()
            snapshot = db.exec(select(SocialSnapshot).where(SocialSnapshot.profile_id == identifier, SocialSnapshot.day == today)).first()
            snapshot = snapshot or SocialSnapshot(profile_id=identifier, day=today)
            snapshot.followers, snapshot.media_count = result['followers'], result['posts']
            db.add(snapshot)
            for item in result['media']:
                row = db.exec(select(SocialMedia).where(SocialMedia.profile_id == identifier, SocialMedia.media_id == item['id'])).first()
                row = row or SocialMedia(profile_id=identifier, media_id=item['id'], kind='post', published_at=item['published_at'])
                if item['likes'] is not None:
                    row.likes = item['likes']
                if item['comments'] is not None:
                    row.comments = item['comments']
                db.add(row)
            for item in result['comments']:
                if item['author'].casefold() == username.casefold():
                    continue
                record = db.exec(select(SocialComment).where(SocialComment.profile_id == identifier, SocialComment.comment_id == item['id'])).first()
                if record:
                    continue
                record = SocialComment(profile_id=identifier, comment_id=item['id'], author=item['author'], text=item['text'],
                                       post_url=item['post_url'], published_at=item['published_at'])
                relevant = commercial_request(record.text)
                record.reason = 'Pedido comercial identificado por regra.' if relevant else 'Sem pedido comercial claro; disponível para revisão.'
                record.status = 'revisar' if relevant else 'informativo'
                db.add(record)
                db.flush()
                fresh = not profile.browser_since or as_utc(record.published_at) >= as_utc(profile.browser_since) - timedelta(minutes=5)
                if relevant and profile.auto_demands and fresh:
                    create_comment_demand(db, record, profile, automatic=True)
                elif relevant and not fresh:
                    record.reason += ' Comentário anterior à conexão: revise antes de criar demanda.'
                    db.add(record)
            profile.stories_ok = False
            profile.comments_detail = result.get('detail', '')
            profile.metrics_complete = (not result['posts'] or bool(result['media'])) and all(item['likes'] is not None and item['comments'] is not None for item in result['media'])
            if not profile.metrics_complete:
                profile.comments_detail += ' Alguns contadores não foram disponibilizados pelo Instagram.'
            profile.status, profile.status_detail, profile.last_sync = 'ok', '', now()
            db.add(profile)
            db.commit()
    except (social_browser.BrowserError, OSError) as error:
        with Session(engine) as db:
            profile = db.get(SocialProfile, identifier)
            if profile and profile.enabled and profile.browser_path == path and profile.username == username and as_utc(profile.browser_since) == connected_at:
                profile.status = error.status if isinstance(error, social_browser.BrowserError) else 'erro'
                profile.status_detail = str(error) if isinstance(error, social_browser.BrowserError) else 'Não foi possível acessar o perfil local do Chrome.'
                db.add(profile)
                db.commit()


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
        with Session(engine) as db:
            query = select(SocialProfile) if identifier is None else select(SocialProfile).where(SocialProfile.id == identifier)
            identifiers = [profile.id for profile in db.exec(query).all()]
        for current in identifiers:
            with Session(engine) as db, _client() as client:
                profile = db.get(SocialProfile, current)
                if not profile:
                    continue
                if not profile.enabled:
                    continue
                if profile.method == 'browser':
                    if identifier is not None or profile.status not in ('login', 'limitado'):
                        _browser_sync(engine, profile.id)
                    continue
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
    all_media = db.exec(select(SocialMedia).where(SocialMedia.profile_id == profile.id)).all()
    recent = [m for m in all_media if as_utc(m.published_at) >= since]
    posts = [m for m in recent if m.kind == 'post']
    return {
        'id': profile.id, 'front_id': profile.front_id, 'network': profile.network, 'username': profile.username,
        'name': profile.name, 'avatar': profile.avatar, 'status': profile.status, 'status_detail': profile.status_detail,
        'last_sync': as_utc(profile.last_sync),
        'method': profile.method, 'enabled': profile.enabled, 'auto_demands': profile.auto_demands,
        'comments_detail': profile.comments_detail, 'interval_minutes': 15,
        'browser_path': profile.browser_path,
        'followers': latest.followers if latest else None,
        'posts': latest.media_count if latest else None,
        'followers_change': latest.followers - base.followers if latest and base else None,
        'change_days': min(7, (latest.day - base.day).days) if latest and base else 0,
        'posts_week': None if profile.method == 'browser' and (not profile.last_sync or latest and latest.media_count and not all_media) else len(posts),
        'stories_week': len([m for m in recent if m.kind == 'story']) if profile.stories_ok else None,
        'likes_week': None if not profile.metrics_complete else sum(m.likes for m in posts),
        'comments_week': None if not profile.metrics_complete else sum(m.comments for m in posts),
    }


def router(engine, session, vault, demo):
    api = APIRouter()

    def writable():
        if demo:
            raise HTTPException(409, 'Perfis reais ficam indisponíveis no modo de demonstração.')

    @api.get('/social/browser/profiles')
    def browser_profiles():
        writable()
        try:
            return social_browser.discover()
        except social_browser.BrowserError as error:
            raise HTTPException(400, str(error)) from None

    @api.post('/social/browser', status_code=201)
    def connect_browser(payload: BrowserProfileInput, db: Session = Depends(session)):
        writable()
        try:
            account = next((item for item in social_browser.discover() if item['account_id'] == payload.account_id), None)
        except social_browser.BrowserError as error:
            raise HTTPException(400, str(error)) from None
        if not account:
            raise HTTPException(404, 'Perfil do Prospect não encontrado neste computador.')
        db.execute(text('BEGIN IMMEDIATE'))
        if db.exec(select(SocialProfile).where(SocialProfile.username == account['username'])).first():
            raise HTTPException(409, 'Esta conta já está conectada. Remova a conexão anterior para mudar a origem.')
        profile = SocialProfile(front_id=payload.front_id, account_id=f"browser:{account['username']}", username=account['username'],
                                name=account['name'], keyring_ref='', method='browser', browser_path=account['path'],
                                browser_since=now(), auto_demands=payload.auto_demands, stories_ok=False, metrics_complete=False)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return output(db, profile)

    @api.put('/social/{identifier}/browser')
    def browser_settings(identifier: int, payload: BrowserSettings, db: Session = Depends(session)):
        writable()
        profile = db.get(SocialProfile, identifier)
        if not profile or profile.method != 'browser':
            raise HTTPException(404, 'Perfil de navegador não encontrado.')
        profile.enabled, profile.auto_demands = payload.enabled, payload.auto_demands
        profile.status = 'aguardando' if payload.enabled else 'pausado'
        profile.status_detail = ''
        db.add(profile)
        db.commit()
        return output(db, profile)

    @api.get('/social/comments')
    def comments(db: Session = Depends(session)):
        records = db.exec(select(SocialComment).order_by(SocialComment.received_at.desc(), SocialComment.id.desc()).limit(200)).all()
        return [{**item.model_dump(), 'published_at': as_utc(item.published_at), 'received_at': as_utc(item.received_at),
                 'front_id': db.get(SocialProfile, item.profile_id).front_id} for item in records if db.get(SocialProfile, item.profile_id)]

    @api.post('/social/comments/{identifier}/{action}')
    def resolve_comment(identifier: int, action: str, db: Session = Depends(session)):
        writable()
        if action not in ('accept', 'dismiss'):
            raise HTTPException(404, 'Ação inválida.')
        db.execute(text('BEGIN IMMEDIATE'))
        comment = db.get(SocialComment, identifier)
        profile = db.get(SocialProfile, comment.profile_id) if comment else None
        if not profile:
            raise HTTPException(404, 'Comentário não encontrado.')
        if action == 'accept':
            create_comment_demand(db, comment, profile)
        elif comment.status != 'demanda':
            comment.status = 'descartado'
            db.add(comment)
        db.commit()
        return {'status': comment.status, 'demand_id': comment.demand_id}

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
        for table in (SocialSnapshot, SocialMedia, SocialComment):
            for row in db.exec(select(table).where(table.profile_id == identifier)).all():
                db.delete(row)
        if profile.keyring_ref:
            vault.delete(profile.keyring_ref)
        db.delete(profile)
        db.commit()

    return api
