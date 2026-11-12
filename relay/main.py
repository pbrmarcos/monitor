"""Fila durável de formulários. Tokens de envio ficam SOMENTE nos servidores dos sites."""
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class Submission(BaseModel):
    submission_id: str = Field(min_length=8, max_length=120, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(default='', max_length=200)
    email: str = Field(min_length=3, max_length=200, pattern=r'^[^@\s]+@[^@\s]+$')
    subject: str = Field(default='Contato pelo site', min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10000)


class Acknowledgement(BaseModel):
    ids: list[int] = Field(max_length=100)


def create_app(database=None, app_token=None, site_tokens=None):
    database = Path(database or os.environ.get('RELAY_DB', '/data/relay.db'))
    app_token = app_token or os.environ.get('RELAY_APP_TOKEN', '')
    site_tokens = site_tokens or json.loads(os.environ.get('RELAY_SITE_TOKENS', '{}'))
    if len(app_token) < 32 or not site_tokens or any(not str(k).isdigit() or int(k) < 1 or not isinstance(v, str) or len(v) < 32 for k, v in site_tokens.items()):
        raise RuntimeError('Configure tokens distintos com pelo menos 32 caracteres e IDs numéricos dos sites.')
    tokens = [app_token, *site_tokens.values()]
    if len(set(tokens)) != len(tokens):
        raise RuntimeError('Cada credencial precisa ser diferente.')
    database.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        db = sqlite3.connect(database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER NOT NULL, submission_id TEXT NOT NULL, payload TEXT NOT NULL, received_at TEXT NOT NULL DEFAULT (strftime(\'%Y-%m-%dT%H:%M:%fZ\',\'now\')), acked INTEGER NOT NULL DEFAULT 0, UNIQUE(site_id,submission_id))')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    rate_lock = threading.Lock()
    rate = {}

    def authorize(value, token):
        if not value or not secrets.compare_digest(value.encode(), f'Bearer {token}'.encode()):
            raise HTTPException(401, 'Credencial inválida.')

    @app.middleware('http')
    async def limit_body(request: Request, call_next):
        # Limite também para transferências sem Content-Length.
        if request.method == 'POST':
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 64000:
                    return JSONResponse({'detail': 'Conteúdo muito grande.'}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        return JSONResponse({'detail': 'Dados do formulário inválidos.'}, status_code=422)

    @app.get('/health')
    def health():
        return {'ok': True}

    @app.post('/forms/{site_id}', status_code=202)
    def submit(site_id: int, payload: Submission, authorization: Annotated[str | None, Header()] = None,
               x_monitor_test: Annotated[str | None, Header()] = None):
        token = site_tokens.get(str(site_id))
        if not token:
            raise HTTPException(401, 'Credencial inválida.')
        authorize(authorization, token)
        with rate_lock:
            minute = int(time.time() // 60)
            stamp, count = rate.get(site_id, (minute, 0))
            count = count if stamp == minute else 0
            if count >= 30:
                raise HTTPException(429, 'Limite de envios atingido.', headers={'Retry-After': '60'})
            rate[site_id] = (minute, count + 1)
        if x_monitor_test:
            return {'accepted': True, 'test': True}  # nunca entra na fila comercial
        with connect() as db:
            db.execute('INSERT OR IGNORE INTO events(site_id,submission_id,payload) VALUES (?,?,?)',
                       (site_id, payload.submission_id, payload.model_dump_json()))
            event = db.execute('SELECT id,payload FROM events WHERE site_id=? AND submission_id=?', (site_id, payload.submission_id)).fetchone()
            if json.loads(event['payload']) != payload.model_dump():
                raise HTTPException(409, 'Este identificador já foi usado por outro envio.')
        return {'accepted': True, 'id': event['id']}

    @app.get('/events')
    def events(after: int = 0, authorization: Annotated[str | None, Header()] = None):
        authorize(authorization, app_token)
        with connect() as db:
            rows = db.execute('SELECT * FROM events WHERE acked=0 AND id>? ORDER BY id LIMIT 100', (after,)).fetchall()
        return [{'id': r['id'], 'site_id': r['site_id'], 'received_at': r['received_at'], **json.loads(r['payload'])} for r in rows]

    @app.post('/events/ack', status_code=204)
    def acknowledge(payload: Acknowledgement, authorization: Annotated[str | None, Header()] = None):
        authorize(authorization, app_token)
        with connect() as db:
            db.executemany('UPDATE events SET acked=1 WHERE id=?', [(identifier,) for identifier in payload.ids])

    return app
