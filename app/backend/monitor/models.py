"""Tabelas do banco local. Datas e horas são sempre UTC."""
from datetime import date, datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Demand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
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
    origin_ref: str = ''
    created_by: str = 'usuario'
    created_at: datetime = Field(default_factory=now)


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    demand_id: int = Field(index=True)
    description: str
    created_at: datetime = Field(default_factory=now)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class EmailAccount(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    front_id: int
    address: str
    host: str
    port: int = 993
    username: str
    keyring_ref: str
    # JSON por pasta: {"INBOX": {"uidvalidity": 1, "uid": 42}}
    last_uids: str = '{}'
    last_sync: datetime | None = None
    status: str = 'aguardando'
    status_detail: str = ''


class Email(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('account_id', 'message_id'),)
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    message_id: str
    sender: str = ''
    recipients: str = ''
    subject: str = ''
    date: datetime | None = Field(default=None, index=True)
    body_text: str = ''
    has_attachments: bool = False
    bulk: bool = False
    folder: str = 'INBOX'
    uid: int = 0
    flags: str = ''
    analysis_status: str = 'pendente'


class EmailAnalysis(SQLModel, table=True):
    email_id: int = Field(primary_key=True)
    categoria: str = 'outro'
    importancia: str = 'revisar'
    motivo: str = ''
    resumo: str = ''
    acao_sugerida: str | None = None
    prazo_texto: str | None = None
    prazo_iso: date | None = None
    trecho_prazo: str | None = None
    criar_demanda: bool = False
    confianca: float = 0.0
    modelo: str = ''
    correcao: str | None = None
    # True enquanto só as regras determinísticas avaliaram a mensagem.
    provisional: bool = True


class AiJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str = 'email'
    ref_id: int = Field(index=True)
    status: str = Field(default='pendente', index=True)
    attempts: int = 0
    error: str = ''
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Suggestion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email_id: int = Field(unique=True)
    front_id: int
    title: str
    contact: str = ''
    summary: str = ''
    due: date | None = None
    status: str = Field(default='pendente', index=True)
    demand_id: int | None = None
    created_at: datetime = Field(default_factory=now)
