import json
import os
import secrets
import socket
import sys
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from . import ai, inbox, mail, storage
from .models import AiJob, Demand, Email, EmailAccount, EmailAnalysis, Event, Setting, Suggestion, as_utc, now
from .secrets_store import KeyringStore, MemoryStore, SecretError

VERSION = '0.2.0-alpha.1'
Stage = Literal['novo', 'qualificacao', 'preparar_proposta', 'proposta_enviada', 'acompanhar', 'ganho', 'perdido']


class DemandInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    front_id: int = Field(ge=1, le=4)
    contact: str = Field(default='', max_length=200)
    channel: Literal['manual', 'email', 'formulario', 'instagram', 'whatsapp'] = 'manual'
    stage: Stage = 'novo'
    priority: Literal['normal', 'alta'] = 'normal'
    due: date | None = None
    next_action: str = Field(default='', max_length=2000)
    return_date: date | None = None
    summary: str = Field(default='', max_length=6000)
    origin_ref: str = Field(default='', max_length=60, pattern=r'^(email:\d+)?$')

    @model_validator(mode='after')
    def validate_demand(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Informe um título.')
        if self.stage == 'acompanhar' and not self.return_date:
            raise ValueError('A etapa Acompanhar exige data de retorno.')
        return self


class SettingsInput(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.:/-]+$')
    priority_senders: list[str] | None = Field(default=None, max_length=100)


class ModelInput(BaseModel):
    model: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.:/-]+$')


class AccountInput(BaseModel):
    front_id: int = Field(ge=1, le=4)
    address: str = Field(min_length=3, max_length=200, pattern=r'^[^@\s]+@[^@\s]+$')
    host: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9.-]+$')
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=500)


class CorrectionInput(BaseModel):
    value: Literal['importante', 'nao_importante']


class StorageInput(BaseModel):
    files_dir: str = Field(min_length=1, max_length=400)


def migrate(engine):
    """Migrações versionadas; cada mudança de esquema acrescenta uma versão."""
    with engine.begin() as connection:
        connection.execute(text('PRAGMA journal_mode=WAL'))
        connection.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)'))
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        # Versão 2: origem e autoria das demandas (tabelas de e-mail vêm do create_all).
        columns = {row[1] for row in connection.execute(text('PRAGMA table_info(demand)'))}
        if 'origin_ref' not in columns:
            connection.execute(text("ALTER TABLE demand ADD COLUMN origin_ref VARCHAR NOT NULL DEFAULT ''"))
        if 'created_by' not in columns:
            connection.execute(text("ALTER TABLE demand ADD COLUMN created_by VARCHAR NOT NULL DEFAULT 'usuario'"))
        for version in (1, 2):
            connection.execute(text('INSERT OR IGNORE INTO schema_migrations VALUES (:v)'), {'v': version})


def seed_demo(db: Session):
    today = date.today()
    for i, (title, stage, front) in enumerate([
        ('Preparar proposta para Ana', 'preparar_proposta', 1),
        ('Revisar briefing do projeto', 'qualificacao', 2),
        ('Atualizar apresentação comercial', 'novo', 3),
        ('Retornar sobre proposta enviada', 'acompanhar', 4),
    ]):
        db.add(Demand(title=title, stage=stage, front_id=front, due=today + timedelta(days=i // 2),
                      return_date=today if stage == 'acompanhar' else None,
                      priority='alta' if i == 0 else 'normal', contact='Contato de demonstração',
                      summary='Registro fictício para explorar o Monitor.'))
    samples = [
        (1, 'Ana Souza <ana@cliente.example>', 'Orçamento para novo projeto',
         'Olá, Marcos! Gostaria de receber um orçamento para nosso novo projeto. Preciso da proposta até sexta.',
         'orcamento', 'acao', 'Pedido de orçamento com prazo.', 'Enviar proposta para Ana'),
        (2, 'Pedro Lima <pedro@cliente.example>', 'Briefing e referências',
         'Segue o briefing para revisão. Podemos alinhar os detalhes na próxima conversa?',
         'cliente', 'importante', 'Cliente enviou material para revisão.', 'Revisar o briefing'),
        (3, 'Boletim de design <newsletter@boletim.example>', 'Referências da semana',
         'Uma seleção de novidades e referências para sua leitura.',
         'publicidade', 'info', 'Boletim informativo.', None),
        (4, 'Carla Dias <carla@fornecedor.example>', 'Sobre a entrega do material',
         'Oi! Acho que conseguimos entregar na semana que vem, mas ainda preciso confirmar.',
         'fornecedor', 'revisar', 'Data ambígua, confira o prazo.', None),
    ]
    for front, sender, subject, body, category, importance, reason, action in samples:
        account = EmailAccount(front_id=front, address=f'contato@frente0{front}.example', host='imap.example',
                               username=f'contato@frente0{front}.example', keyring_ref='demo', status='demonstracao')
        db.add(account)
        db.flush()
        message = Email(account_id=account.id, message_id=f'<demo-{front}@example>', sender=sender, subject=subject,
                        recipients=account.address, date=now() - timedelta(hours=front * 3), body_text=body,
                        analysis_status='analisado', bulk=category == 'publicidade')
        db.add(message)
        db.flush()
        analysis = EmailAnalysis(email_id=message.id, categoria=category, importancia=importance, motivo=reason,
                                 resumo=body[:240], acao_sugerida=action, criar_demanda=importance == 'acao',
                                 confianca=0.9, modelo='demonstração', provisional=False,
                                 prazo_texto='sexta' if front == 1 else 'semana que vem' if front == 4 else None,
                                 prazo_iso=today + timedelta(days=(4 - today.weekday()) % 7 or 7) if front == 1 else None,
                                 trecho_prazo='Preciso da proposta até sexta.' if front == 1 else None)
        db.add(analysis)
        inbox.upsert_suggestion(db, message, analysis, front)
    db.add(Setting(key='demo_seeded', value='1'))
    db.commit()


def create_app(data_dir: Path | None = None, token: str | None = None, demo: bool | None = None,
               secret_store=None, connector=mail.connect, default_files_dir: str | None = None, workers: bool = False):
    folder = data_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'Monitor'
    folder.mkdir(parents=True, exist_ok=True)
    demo = os.getenv('MONITOR_DEMO') == '1' if demo is None else demo
    # Banco de demonstração separado: dados fictícios nunca se misturam aos reais.
    database = folder / ('demo.db' if demo else 'monitor.db')
    engine = create_engine(f'sqlite:///{database}', connect_args={'check_same_thread': False, 'timeout': 15})
    session_token = token or secrets.token_urlsafe(32)
    security = HTTPBearer(auto_error=False)
    vault = secret_store or (MemoryStore() if demo else KeyringStore())
    scheduler = None

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        if not credentials or not secrets.compare_digest(credentials.credentials, session_token):
            raise HTTPException(401, 'Sessão inválida.')

    def session():
        with Session(engine) as db:
            yield db

    def files_dir(db: Session) -> tuple[Path | None, str | None]:
        saved = inbox.setting(db, 'files_dir')
        if saved:
            return Path(saved), 'configuracao'
        return (Path(default_files_dir), 'instalador') if default_files_dir else (None, None)

    def backup_if_due():
        if demo:
            return
        with Session(engine) as db:
            target, _ = files_dir(db)
        if target and target.is_dir() and storage.last_backup(target) != date.today().isoformat():
            try:
                storage.backup(database, target)
            except storage.StorageError:
                pass

    @asynccontextmanager
    async def lifespan(app):
        nonlocal scheduler
        migrate(engine)
        with Session(engine) as db:
            if demo and not db.get(Setting, 'demo_seeded'):
                seed_demo(db)
        inbox.reset_interrupted(engine)
        if workers:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            scheduler = BackgroundScheduler(job_defaults={'coalesce': True, 'max_instances': 1, 'misfire_grace_time': 60})
            start = datetime.now() + timedelta(seconds=8)
            if not demo:
                scheduler.add_job(lambda: inbox.sync_all(engine, vault, connector), IntervalTrigger(minutes=2), next_run_time=start)
                scheduler.add_job(lambda: inbox.process_queue(engine), IntervalTrigger(seconds=20), next_run_time=start)
                scheduler.add_job(backup_if_due, IntervalTrigger(hours=3), next_run_time=start + timedelta(seconds=30))
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        engine.dispose()

    app = FastAPI(title='Monitor', lifespan=lifespan, dependencies=[Depends(authorize)], docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:1420', 'http://127.0.0.1:1420', 'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'], allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
    app.state.token = session_token
    app.state.engine = engine
    app.state.vault = vault

    @app.get('/health')
    def health():
        return {'ok': True, 'demo': demo, 'version': VERSION}

    # ---- Demandas -------------------------------------------------------

    @app.get('/demands')
    def demands(db: Session = Depends(session)):
        return db.exec(select(Demand).order_by(Demand.id.desc())).all()

    def close_suggestion(db: Session, item: Demand):
        if item.origin_ref.startswith('email:'):
            pending = db.exec(select(Suggestion).where(Suggestion.email_id == int(item.origin_ref[6:]), Suggestion.status == 'pendente')).first()
            if pending:
                pending.status, pending.demand_id = 'aceita', item.id
                db.add(pending)

    @app.post('/demands', status_code=201)
    def create(payload: DemandInput, db: Session = Depends(session)):
        item = Demand(**payload.model_dump())
        db.add(item)
        db.flush()
        origin = 'Demanda criada pelo usuário a partir de um e-mail.' if item.origin_ref else 'Demanda criada pelo usuário.'
        db.add(Event(demand_id=item.id, description=origin))
        close_suggestion(db, item)
        db.commit()
        db.refresh(item)
        return item

    @app.put('/demands/{identifier}')
    def update(identifier: int, payload: DemandInput, db: Session = Depends(session)):
        item = db.get(Demand, identifier)
        if not item:
            raise HTTPException(404, 'Demanda não encontrada.')
        values = payload.model_dump(exclude={'origin_ref'})
        changes = [key for key, value in values.items() if getattr(item, key) != value]
        previous_stage = item.stage
        for key, value in values.items():
            setattr(item, key, value)
        if changes:
            description = f'Etapa: {previous_stage} → {item.stage}.' if 'stage' in changes else 'Dados da demanda atualizados.'
            db.add(Event(demand_id=identifier, description=description))
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @app.delete('/demands/{identifier}', status_code=204)
    def delete(identifier: int, db: Session = Depends(session)):
        item = db.get(Demand, identifier)
        if not item:
            raise HTTPException(404, 'Demanda não encontrada.')
        for event in db.exec(select(Event).where(Event.demand_id == identifier)).all():
            db.delete(event)
        db.delete(item)
        db.commit()

    @app.get('/demands/{identifier}/events')
    def events(identifier: int, db: Session = Depends(session)):
        items = db.exec(select(Event).where(Event.demand_id == identifier).order_by(Event.id.desc())).all()
        return [{**item.model_dump(), 'created_at': as_utc(item.created_at)} for item in items]

    # ---- Configurações e IA local ---------------------------------------

    @app.get('/settings')
    def settings(db: Session = Depends(session)):
        return {'model': inbox.setting(db, 'model', ai.DEFAULT_MODEL), 'priority_senders': inbox.priority_senders(db)}

    @app.put('/settings')
    def save_settings(payload: SettingsInput, db: Session = Depends(session)):
        if payload.model is not None:
            db.merge(Setting(key='model', value=payload.model))
        if payload.priority_senders is not None:
            cleaned = sorted({value.strip().lower()[:200] for value in payload.priority_senders if value.strip()})
            db.merge(Setting(key='priority_senders', value=json.dumps(cleaned)))
        db.commit()
        return settings(db)

    @app.get('/ollama')
    async def ollama():
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                version = await client.get(f'{ai.OLLAMA}/api/version')
                version.raise_for_status()
                tags = await client.get(f'{ai.OLLAMA}/api/tags')
                tags.raise_for_status()
                return {'available': True, 'models': [m['name'] for m in tags.json().get('models', [])]}
        except (httpx.HTTPError, ValueError, KeyError):
            return {'available': False, 'models': []}

    @app.post('/ollama/pull')
    async def pull(payload: ModelInput):
        async def stream():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5), trust_env=False) as client:
                    async with client.stream('POST', f'{ai.OLLAMA}/api/pull', json={'model': payload.model}) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                yield line + '\n'
            except httpx.HTTPError:
                yield json.dumps({'error': 'Não foi possível baixar o modelo. Verifique o Ollama e o nome informado.'}) + '\n'
        return StreamingResponse(stream(), media_type='application/x-ndjson')

    # ---- Contas de e-mail ------------------------------------------------

    def account_out(account: EmailAccount):
        return {'id': account.id, 'front_id': account.front_id, 'address': account.address, 'host': account.host,
                'port': account.port, 'username': account.username, 'status': account.status,
                'status_detail': account.status_detail, 'last_sync': as_utc(account.last_sync)}

    def real_accounts_only():
        if demo:
            raise HTTPException(409, 'Contas reais ficam indisponíveis no modo de demonstração.')

    @app.get('/email-accounts')
    def accounts(db: Session = Depends(session)):
        return [account_out(account) for account in db.exec(select(EmailAccount).order_by(EmailAccount.id)).all()]

    @app.post('/email-accounts/test')
    def test_account(payload: AccountInput):
        real_accounts_only()
        try:
            mail.check_login(payload.host, payload.port, payload.username, payload.password, connector)
        except mail.MailError as error:
            raise HTTPException(400, str(error)) from None
        return {'ok': True}

    @app.post('/email-accounts', status_code=201)
    def add_account(payload: AccountInput, db: Session = Depends(session)):
        real_accounts_only()
        if db.exec(select(EmailAccount).where(EmailAccount.address == payload.address.lower())).first():
            raise HTTPException(409, 'Esta conta já está cadastrada.')
        try:
            mail.check_login(payload.host, payload.port, payload.username, payload.password, connector)
        except mail.MailError as error:
            raise HTTPException(400, str(error)) from None
        reference = f'imap:{payload.address.lower()}'
        try:
            vault.set(reference, payload.password)
        except SecretError as error:
            raise HTTPException(500, str(error)) from None
        account = EmailAccount(front_id=payload.front_id, address=payload.address.lower(), host=payload.host.lower(),
                               port=payload.port, username=payload.username, keyring_ref=reference)
        db.add(account)
        db.commit()
        db.refresh(account)
        return account_out(account)

    @app.delete('/email-accounts/{identifier}', status_code=204)
    def remove_account(identifier: int, db: Session = Depends(session)):
        real_accounts_only()
        account = db.get(EmailAccount, identifier)
        if not account:
            raise HTTPException(404, 'Conta não encontrada.')
        # Remove só os registros locais; nada é alterado no servidor de e-mail.
        for message in db.exec(select(Email).where(Email.account_id == identifier)).all():
            if row := db.get(EmailAnalysis, message.id):
                db.delete(row)
            for row in db.exec(select(AiJob).where(AiJob.ref_id == message.id)).all():
                db.delete(row)
            for row in db.exec(select(Suggestion).where(Suggestion.email_id == message.id, Suggestion.status == 'pendente')).all():
                db.delete(row)
            db.delete(message)
        vault.delete(account.keyring_ref)
        db.delete(account)
        db.commit()

    @app.post('/emails/sync')
    def sync_now():
        real_accounts_only()
        created = inbox.sync_all(engine, vault, connector)
        threading.Thread(target=inbox.process_queue, args=(engine,), daemon=True).start()
        return {'new': created}

    # ---- E-mails, correções e sugestões ----------------------------------

    @app.get('/emails')
    def emails(db: Session = Depends(session)):
        messages = db.exec(select(Email).order_by(Email.date.desc(), Email.id.desc()).limit(300)).all()
        fronts = {account.id: account for account in db.exec(select(EmailAccount)).all()}
        linked = {d.origin_ref: d.id for d in db.exec(select(Demand).where(Demand.origin_ref != '')).all()}
        pending = {s.email_id: s.id for s in db.exec(select(Suggestion).where(Suggestion.status == 'pendente')).all()}
        result = []
        for message in messages:
            analysis = db.get(EmailAnalysis, message.id)
            account = fronts.get(message.account_id)
            result.append({
                'id': message.id, 'account_id': message.account_id, 'account': account.address if account else '',
                'front_id': account.front_id if account else 1, 'sender': message.sender, 'subject': message.subject,
                'date': as_utc(message.date), 'body': message.body_text, 'has_attachments': message.has_attachments,
                'analysis_status': message.analysis_status, 'analysis': analysis.model_dump(exclude={'email_id'}) if analysis else None,
                'demand_id': linked.get(f'email:{message.id}'), 'suggestion_id': pending.get(message.id),
            })
        return result

    @app.post('/emails/{identifier}/correction')
    def correct(identifier: int, payload: CorrectionInput, db: Session = Depends(session)):
        analysis = db.get(EmailAnalysis, identifier)
        if not analysis:
            raise HTTPException(404, 'E-mail não encontrado.')
        analysis.correcao = payload.value
        if payload.value == 'importante':
            if analysis.importancia in ('info', 'revisar'):
                analysis.importancia = 'importante'
        else:
            analysis.importancia = 'info'
            for row in db.exec(select(Suggestion).where(Suggestion.email_id == identifier, Suggestion.status == 'pendente')).all():
                row.status = 'descartada'
                db.add(row)
        db.add(analysis)
        db.commit()
        return {'importancia': analysis.importancia, 'correcao': analysis.correcao}

    def suggestion_out(item: Suggestion):
        return {**item.model_dump(), 'created_at': as_utc(item.created_at)}

    @app.get('/suggestions')
    def suggestions(db: Session = Depends(session)):
        return [suggestion_out(item) for item in db.exec(select(Suggestion).where(Suggestion.status == 'pendente').order_by(Suggestion.id.desc())).all()]

    def pending_suggestion(identifier: int, db: Session) -> Suggestion:
        item = db.get(Suggestion, identifier)
        if not item or item.status != 'pendente':
            raise HTTPException(404, 'Sugestão não encontrada.')
        return item

    @app.post('/suggestions/{identifier}/accept', status_code=201)
    def accept(identifier: int, db: Session = Depends(session)):
        item = pending_suggestion(identifier, db)
        demand = Demand(title=item.title, front_id=item.front_id, contact=item.contact, channel='email',
                        due=item.due, summary=item.summary, origin_ref=f'email:{item.email_id}', created_by='ia')
        db.add(demand)
        db.flush()
        db.add(Event(demand_id=demand.id, description='Demanda sugerida pela análise do e-mail e aceita pelo usuário.'))
        item.status, item.demand_id = 'aceita', demand.id
        db.add(item)
        db.commit()
        db.refresh(demand)
        return demand

    @app.post('/suggestions/{identifier}/dismiss', status_code=204)
    def dismiss(identifier: int, db: Session = Depends(session)):
        item = pending_suggestion(identifier, db)
        item.status = 'descartada'
        db.add(item)
        db.commit()

    @app.get('/ai/status')
    def ai_status(db: Session = Depends(session)):
        jobs = db.exec(select(AiJob.status)).all()
        return {'pending': sum(status in ('pendente', 'processando') for status in jobs), 'failed': jobs.count('erro')}

    # ---- Pasta de arquivos ------------------------------------------------

    def storage_out(db: Session):
        target, source = files_dir(db)
        ready = bool(target and target.is_dir())
        return {'files_dir': str(target) if target else None, 'source': source, 'ready': ready,
                'in_onedrive': bool(target and storage.in_onedrive(target)),
                'last_backup': storage.last_backup(target) if ready else None, 'suggestion': storage.suggestion()}

    @app.get('/storage')
    def get_storage(db: Session = Depends(session)):
        return storage_out(db)

    @app.put('/storage')
    def set_storage(payload: StorageInput, db: Session = Depends(session)):
        try:
            target = storage.prepare(payload.files_dir)
        except storage.StorageError as error:
            raise HTTPException(400, str(error)) from None
        db.merge(Setting(key='files_dir', value=str(target)))
        db.commit()
        return storage_out(db)

    def ready_dir(db: Session) -> Path:
        target, _ = files_dir(db)
        if not target:
            raise HTTPException(409, 'Escolha primeiro a pasta de arquivos nas Configurações.')
        try:
            return storage.prepare(str(target))
        except storage.StorageError as error:
            raise HTTPException(400, str(error)) from None

    @app.post('/storage/backup')
    def backup_now(db: Session = Depends(session)):
        if demo:
            raise HTTPException(409, 'O modo de demonstração não gera backups.')
        try:
            return {'file': str(storage.backup(database, ready_dir(db)))}
        except storage.StorageError as error:
            raise HTTPException(400, str(error)) from None

    @app.post('/storage/export-demands')
    def export_demands(db: Session = Depends(session)):
        rows = [item.model_dump() for item in db.exec(select(Demand).order_by(Demand.id)).all()]
        try:
            return {'file': str(storage.export_demands(rows, ready_dir(db)))}
        except storage.StorageError as error:
            raise HTTPException(400, str(error)) from None

    return app


def run():
    token = secrets.token_urlsafe(32)
    app = create_app(token=token, default_files_dir=storage.installer_choice(), workers=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    # O handshake vai só para o pipe do processo pai, nunca para um arquivo de log.
    print(json.dumps({'port': sock.getsockname()[1], 'token': token}), flush=True)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
    if os.getenv('MONITOR_PARENT_PIPE') == '1':
        def watch_parent():
            try:
                sys.stdin.buffer.read()
            finally:
                server.should_exit = True
        threading.Thread(target=watch_parent, daemon=True).start()
    server.run(sockets=[sock])


if __name__ == '__main__':
    run()
