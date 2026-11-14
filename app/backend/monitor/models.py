"""Tabelas do banco local. Datas e horas são sempre UTC."""
from datetime import date, datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


# Nomes padrão das frentes; o usuário pode trocá-los em Configurações (prefs.front_names).
FRONTS = {1: 'Rocha Comercial', 2: 'Nextlink', 3: 'Carteira Pronta', 4: 'WebQ'}


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Demand(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
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
    # Leitura da pasta de enviados: '' (ainda não lida), 'ok', 'sem_pasta' ou 'erro'.
    sent_status: str = ''


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


class SentEmail(SQLModel, table=True):
    """Mensagem escrita pelo usuário, lida da pasta de enviados para aprender o estilo. Fica só neste computador."""
    __table_args__ = (UniqueConstraint('account_id', 'message_id'),)
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    message_id: str
    recipients: str = ''
    subject: str = ''
    date: datetime | None = Field(default=None, index=True)
    body_text: str = ''
    in_reply_to: str = ''


class EmailStyle(SQLModel, table=True):
    """Como o usuário escreve em uma conta: perfil descrito pela IA local e padrões contados nos enviados."""
    account_id: int = Field(primary_key=True)
    profile: str = ''
    greeting: str = ''
    closing: str = ''
    words: int = 0
    samples: int = 0
    edited: bool = False
    updated_at: datetime | None = None


class EmailDraft(SQLModel, table=True):
    """Rascunho de resposta. O Monitor não envia e-mails."""
    email_id: int = Field(primary_key=True)
    body: str = ''
    updated_at: datetime = Field(default_factory=now)


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


class Reminder(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    text: str
    when: datetime = Field(index=True)
    demand_id: int | None = Field(default=None, index=True)
    status: str = Field(default='pendente', index=True)
    origin_key: str | None = Field(default=None, unique=True)
    revision: int = 0
    created_at: datetime = Field(default_factory=now)


class Notice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True)
    kind: str
    title: str
    body: str
    reminder_id: int | None = None
    demand_id: int | None = None
    read: bool = False
    desktop_status: str = Field(default='pendente', index=True)
    created_at: datetime = Field(default_factory=now)


class Site(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    url: str
    front_id: int
    expected_text: str = ''
    enabled: bool = True
    created_at: datetime = Field(default_factory=now)


class SiteCheck(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    site_id: int = Field(index=True)
    checked_at: datetime = Field(default_factory=now, index=True)
    ok: bool
    status_code: int | None = None
    latency_ms: int | None = None
    detail: str = ''
    ssl_expires: datetime | None = None


class SiteIncident(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    site_id: int = Field(index=True)
    opened_at: datetime = Field(default_factory=now)
    closed_at: datetime | None = None
    detail: str


class FormEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_key: str = Field(unique=True)
    site_id: int
    front_id: int
    name: str
    email: str
    subject: str
    message: str
    received_at: datetime
    status: str = 'pendente'
    demand_id: int | None = None


class SocialProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    front_id: int
    network: str = 'instagram'
    account_id: str = Field(unique=True)
    username: str
    name: str = ''
    avatar: str = ''  # data URI; o endereço da foto no Instagram expira
    keyring_ref: str
    token_at: datetime | None = None
    stories_ok: bool = True
    status: str = 'aguardando'
    status_detail: str = ''
    last_sync: datetime | None = None
    method: str = 'api'
    browser_path: str = ''
    auto_demands: bool = False
    enabled: bool = True
    comments_detail: str = ''
    browser_since: datetime | None = None
    metrics_complete: bool = True


class SocialSnapshot(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('profile_id', 'day'),)
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(index=True)
    day: date
    followers: int = 0
    media_count: int = 0


class SocialMedia(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('profile_id', 'media_id'),)
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(index=True)
    media_id: str
    kind: str  # post | story
    published_at: datetime
    likes: int = 0
    comments: int = 0


class SocialComment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('profile_id', 'comment_id'), {'sqlite_autoincrement': True})
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(index=True)
    comment_id: str
    author: str
    text: str
    post_url: str
    published_at: datetime
    received_at: datetime = Field(default_factory=now)
    status: str = 'revisar'
    reason: str = ''
    demand_id: int | None = None


class Conversation(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    mode: str = 'work'  # work: com os dados do Monitor; general: conversa livre
    title: str = ''
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now, index=True)


class ChatTurn(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(index=True)
    role: str  # user/assistant, preference_user/preference_assistant, rule ou error
    content: str
    created_at: datetime = Field(default_factory=now)


class ChatMetrics(SQLModel, table=True):
    answer_id: int = Field(primary_key=True)
    data: str = '{}'


class ChatDraft(SQLModel, table=True):
    answer_id: int = Field(primary_key=True)
    data: str = '{}'


class AssistantRun(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int | None = Field(default=None, index=True)
    answer_id: int | None = Field(default=None, index=True)
    kind: str = 'chat'
    status: str = 'running'
    model: str = ''
    detail: str = ''
    metrics: str = '{}'
    skills: str = '[]'
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None


class AssistantSkill(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ''
    keywords: str
    instructions: str
    source_markdown: str = ''
    source_name: str = ''


class ChatAttachment(SQLModel, table=True):
    """Arquivo ou imagem anexado a uma pergunta. Lido e guardado só neste computador."""
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int | None = Field(default=None, index=True)
    turn_id: int | None = Field(default=None, index=True)  # vazio enquanto o anexo não foi enviado
    name: str
    kind: str  # text | pdf | docx | xlsx | image
    mime: str = ''
    size: int = 0
    pages: int = 0
    truncated: bool = False
    text: str = ''
    image: str = ''  # base64 para o modelo de visão
    created_at: datetime = Field(default_factory=now)


class AssistantRule(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    """Preferência duradoura que o assistente segue em todas as conversas."""
    id: int | None = Field(default=None, primary_key=True)
    text: str
    source: str = 'assistente'  # assistente | usuario
    conversation_id: int | None = None
    created_at: datetime = Field(default_factory=now)


class CalendarLink(SQLModel, table=True):
    """Evento do Google Agenda que espelha uma demanda."""
    demand_id: int = Field(primary_key=True)
    event_id: str
    fingerprint: str = ''
    synced_at: datetime | None = None


class ReminderCalendarLink(SQLModel, table=True):
    reminder_id: int = Field(primary_key=True)
    event_id: str
    duration_minutes: int = 30
    fingerprint: str = ''
    synced_at: datetime | None = None


class AssistantAction(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(index=True)
    question_id: int = Field(unique=True)
    answer_id: int | None = None
    kind: str
    status: str = 'pending'
    arguments: str = '{}'
    result: str = '{}'
    created_at: datetime = Field(default_factory=now)
