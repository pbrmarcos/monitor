"""Coleta das contas, fila de análise (um item por vez) e sugestões de demanda."""
import json
import threading
import time
from datetime import date

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from . import ai, mail
from .models import AiJob, Demand, Email, EmailAccount, EmailAnalysis, Setting, Suggestion, now, as_utc
from .rules import Context, decide

CLOSED = ('ganho', 'perdido')
ANALYSIS_FIELDS = ('categoria', 'importancia', 'motivo', 'resumo', 'acao_sugerida', 'prazo_texto', 'prazo_iso',
                   'trecho_prazo', 'criar_demanda', 'confianca')
_sync_lock = threading.Lock()
_queue_lock = threading.Lock()


def setting(db: Session, key: str, default: str = '') -> str:
    item = db.get(Setting, key)
    return item.value if item else default


def priority_senders(db: Session) -> list[str]:
    try:
        return [str(value) for value in json.loads(setting(db, 'priority_senders', '[]'))]
    except ValueError:
        return []


def context(db: Session, reference: date | None = None) -> Context:
    contacts = [d.contact for d in db.exec(select(Demand).where(Demand.stage.not_in(CLOSED))).all() if d.contact.strip()]
    return Context(today=reference or date.today(), priority_senders=priority_senders(db), open_contacts=contacts)


def reference_date(message: Email) -> date:
    return as_utc(message.date).astimezone().date() if message.date else date.today()


def upsert_suggestion(db: Session, message: Email, analysis: EmailAnalysis, front_id: int) -> None:
    """A IA e as regras só sugerem: a demanda nasce quando o usuário aceita."""
    wanted = analysis.importancia == 'acao' or (analysis.criar_demanda and analysis.importancia == 'importante')
    existing = db.exec(select(Suggestion).where(Suggestion.email_id == message.id)).first()
    if existing:
        if existing.status in ('pendente', 'retirada'):
            existing.status = 'pendente' if wanted else 'retirada'
            existing.title = (analysis.acao_sugerida or message.subject)[:200]
            existing.summary = analysis.resumo
            existing.due = analysis.prazo_iso
            db.add(existing)
        return
    if not wanted or db.exec(select(Demand).where(Demand.origin_ref == f'email:{message.id}')).first():
        return
    db.add(Suggestion(email_id=message.id, front_id=front_id, title=(analysis.acao_sugerida or message.subject)[:200],
                      contact=message.sender[:200], summary=analysis.resumo, due=analysis.prazo_iso))


def store_message(db: Session, account: EmailAccount, data: dict, rules: Context) -> bool:
    if db.exec(select(Email).where(Email.account_id == account.id, Email.message_id == data['message_id'])).first():
        return False
    message = Email(account_id=account.id, **data)
    db.add(message)
    db.flush()
    # Sem IA o sistema continua útil: as regras dão uma análise provisória.
    message_rules = Context(today=reference_date(message), priority_senders=rules.priority_senders, open_contacts=rules.open_contacts)
    decision = decide(message.sender, message.subject, message.body_text, message.bulk, None, message_rules)
    analysis = EmailAnalysis(email_id=message.id, provisional=True, **{key: decision[key] for key in ANALYSIS_FIELDS})
    db.add(analysis)
    db.add(AiJob(ref_id=message.id))
    upsert_suggestion(db, message, analysis, account.front_id)
    return True


def sync_account(engine, account_id: int, secrets, connector=mail.connect) -> int:
    with _sync_lock, Session(engine) as db:
        account = db.get(EmailAccount, account_id)
        if not account:
            return 0
        password = secrets.get(account.keyring_ref)
        try:
            if not password:
                raise mail.MailError('Senha não encontrada no Gerenciador de Credenciais. Remova e adicione a conta novamente.')
            messages, state = mail.fetch_new(account.host, account.port, account.username, password,
                                             json.loads(account.last_uids or '{}'), connector)
        except mail.MailError as error:
            account.status, account.status_detail = 'erro', str(error)
            db.add(account)
            db.commit()
            return 0
        rules = context(db)
        created = sum(store_message(db, account, data, rules) for data in messages)
        account.last_uids = json.dumps(state)
        account.last_sync, account.status, account.status_detail = now(), 'ok', ''
        db.add(account)
        db.commit()
        return created


def sync_all(engine, secrets, connector=mail.connect) -> int:
    with Session(engine) as db:
        identifiers = [account.id for account in db.exec(select(EmailAccount)).all()]
    return sum(sync_account(engine, identifier, secrets, connector) for identifier in identifiers)


def _examples(db: Session) -> list[dict]:
    """Correções do usuário viram exemplos para o modelo, até 10 por tipo."""
    examples = []
    for correction in ('importante', 'nao_importante'):
        rows = db.exec(select(EmailAnalysis).where(EmailAnalysis.correcao == correction)
                       .order_by(EmailAnalysis.email_id.desc()).limit(10)).all()
        for row in rows:
            message = db.get(Email, row.email_id)
            account = db.get(EmailAccount, message.account_id) if message else None
            if message:
                answer = {key: getattr(row, key) for key in ANALYSIS_FIELDS}
                answer['prazo_iso'] = answer['prazo_iso'].isoformat() if answer['prazo_iso'] else None
                answer['confianca'] = 0.95
                examples.append({'sender': message.sender, 'account': account.address if account else '',
                                 'subject': message.subject, 'body': message.body_text,
                                 'answer': json.dumps(answer, ensure_ascii=False)})
    return examples


def reset_interrupted(engine) -> None:
    with Session(engine) as db:
        for job in db.exec(select(AiJob).where(AiJob.status == 'processando')).all():
            job.status = 'pendente'
            db.add(job)
        db.commit()


def _process_one(db: Session) -> str:
    job = db.exec(select(AiJob).where(AiJob.status == 'pendente').order_by(AiJob.id)).first()
    if not job:
        return 'vazia'
    message = db.get(Email, job.ref_id)
    account = db.get(EmailAccount, message.account_id) if message else None
    analysis = db.get(EmailAnalysis, job.ref_id) if message else None
    if not message or not analysis:
        job.status, job.error = 'erro', 'Mensagem removida.'
        db.add(job)
        db.commit()
        return 'pulada'
    job.status, job.updated_at = 'processando', now()
    db.add(job)
    db.commit()
    model = setting(db, 'model', ai.DEFAULT_MODEL)
    try:
        answer = ai.analyze(message.sender, account.address if account else '', message.subject,
                            message.body_text, model, reference_date(message), _examples(db))
    except ai.OllamaUnavailable:
        job.status = 'pendente'
        db.add(job)
        db.commit()
        return 'indisponivel'
    except ai.InvalidAnalysis as error:
        job.status, job.error, job.attempts = 'erro', str(error), job.attempts + 1
        message.analysis_status = 'erro'
        db.add_all([job, message])
        db.commit()
        return 'pulada'
    # A correction or account removal can happen while the local model is working.
    message_id, job_id = message.id, job.id
    db.expire_all()
    message, job = db.get(Email, message_id), db.get(AiJob, job_id)
    analysis = db.get(EmailAnalysis, message_id)
    if not message or not job or not analysis:
        return 'pulada'
    decision = decide(message.sender, message.subject, message.body_text, message.bulk, answer.model_dump(), context(db, reference_date(message)))
    if analysis.correcao:
        # A correção do usuário vale mais que uma nova análise.
        decision['importancia'] = analysis.importancia
    for key in ANALYSIS_FIELDS:
        setattr(analysis, key, decision[key])
    analysis.modelo, analysis.provisional = model, False
    message.analysis_status = 'analisado'
    job.status, job.attempts, job.updated_at = 'concluido', job.attempts + 1, now()
    db.add_all([analysis, message, job])
    if not analysis.correcao:
        upsert_suggestion(db, message, analysis, account.front_id if account else 1)
    db.commit()
    return 'feita'


def process_queue(engine, limit: int = 25, seconds: float = 100) -> int:
    """Processa a fila um item por vez. Com o Ollama fora do ar, os itens continuam pendentes."""
    if not _queue_lock.acquire(blocking=False):
        return 0
    done, started = 0, time.monotonic()
    try:
        while done < limit and time.monotonic() - started < seconds:
            with Session(engine) as db:
                try:
                    outcome = _process_one(db)
                except SQLAlchemyError:
                    # Ex.: a conta foi removida durante a análise. A fila segue na próxima rodada.
                    db.rollback()
                    break
            if outcome in ('vazia', 'indisponivel'):
                break
            done += outcome == 'feita'
    finally:
        _queue_lock.release()
    return done
