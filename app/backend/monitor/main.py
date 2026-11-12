import asyncio
import json
import os
import secrets
import socket
import sys
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select, Field as SQLField

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

    @model_validator(mode='after')
    def validate_demand(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Informe um título.')
        if self.stage == 'acompanhar' and not self.return_date:
            raise ValueError('A etapa Acompanhar exige data de retorno.')
        return self


class Demand(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    title: str
    front_id: int
    contact: str = ''
    channel: str = 'manual'
    stage: str = 'novo'
    priority: str = 'normal'
    due: date | None = None
    next_action: str = ''
    return_date: date | None = None
    summary: str = ''
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Event(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    demand_id: int = SQLField(index=True)
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Setting(SQLModel, table=True):
    key: str = SQLField(primary_key=True)
    value: str


class SettingsInput(BaseModel):
    model: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.:/-]+$')


def create_app(data_dir: Path | None = None, token: str | None = None, demo: bool | None = None):
    folder = data_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'Monitor'
    folder.mkdir(parents=True, exist_ok=True)
    demo = os.getenv('MONITOR_DEMO') == '1' if demo is None else demo
    # Separate demo database so sample data cannot mix with a real workspace.
    engine = create_engine(f"sqlite:///{folder / ('demo.db' if demo else 'monitor.db')}", connect_args={'check_same_thread': False})
    session_token = token or secrets.token_urlsafe(32)
    security = HTTPBearer(auto_error=False)

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        if not credentials or not secrets.compare_digest(credentials.credentials, session_token):
            raise HTTPException(401, 'Sessão inválida.')

    def session():
        with Session(engine) as db:
            yield db

    @asynccontextmanager
    async def lifespan(app):
        # Transactional versioned migration; future schema changes append versions.
        with engine.begin() as connection:
            connection.execute(text('PRAGMA journal_mode=WAL'))
            connection.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)'))
        SQLModel.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text('INSERT OR IGNORE INTO schema_migrations VALUES (1)'))
        with Session(engine) as db:
            if demo and not db.get(Setting, 'demo_seeded'):
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
                db.add(Setting(key='demo_seeded', value='1'))
                db.commit()
        yield
        engine.dispose()

    app = FastAPI(title='Monitor', lifespan=lifespan, dependencies=[Depends(authorize)], docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:1420', 'http://127.0.0.1:1420', 'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'], allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
    app.state.token = session_token

    @app.get('/health')
    def health():
        return {'ok': True, 'demo': demo, 'version': '0.1.0-alpha.1'}

    @app.get('/demands')
    def demands(db: Session = Depends(session)):
        return db.exec(select(Demand).order_by(Demand.id.desc())).all()

    @app.post('/demands', status_code=201)
    def create(payload: DemandInput, db: Session = Depends(session)):
        item = Demand(**payload.model_dump())
        db.add(item)
        db.flush()
        db.add(Event(demand_id=item.id, description='Demanda criada pelo usuário.'))
        db.commit()
        db.refresh(item)
        return item

    @app.put('/demands/{identifier}')
    def update(identifier: int, payload: DemandInput, db: Session = Depends(session)):
        item = db.get(Demand, identifier)
        if not item:
            raise HTTPException(404, 'Demanda não encontrada.')
        changes = [key for key, value in payload.model_dump().items() if getattr(item, key) != value]
        previous_stage = item.stage
        for key, value in payload.model_dump().items():
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
        return db.exec(select(Event).where(Event.demand_id == identifier).order_by(Event.id.desc())).all()

    @app.get('/settings')
    def settings(db: Session = Depends(session)):
        model = db.get(Setting, 'model')
        return {'model': model.value if model else 'qwen3.5:4b-q4_K_M'}

    @app.put('/settings')
    def save_settings(payload: SettingsInput, db: Session = Depends(session)):
        db.merge(Setting(key='model', value=payload.model))
        db.commit()
        return payload

    @app.get('/ollama')
    async def ollama():
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                version = await client.get('http://127.0.0.1:11434/api/version')
                version.raise_for_status()
                tags = await client.get('http://127.0.0.1:11434/api/tags')
                tags.raise_for_status()
                return {'available': True, 'models': [m['name'] for m in tags.json().get('models', [])]}
        except (httpx.HTTPError, ValueError, KeyError):
            return {'available': False, 'models': []}

    @app.post('/ollama/pull')
    async def pull(payload: SettingsInput):
        async def stream():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5), trust_env=False) as client:
                    async with client.stream('POST', 'http://127.0.0.1:11434/api/pull', json={'model': payload.model}) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                yield line + '\n'
            except httpx.HTTPError:
                yield json.dumps({'error': 'Não foi possível baixar o modelo. Verifique o Ollama e o nome informado.'}) + '\n'
        return StreamingResponse(stream(), media_type='application/x-ndjson')

    return app


def run():
    token = secrets.token_urlsafe(32)
    app = create_app(token=token)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    # Handshake goes only to the parent sidecar pipe, never a log file.
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
