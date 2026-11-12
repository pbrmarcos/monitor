"""Durable reminders and deterministic daily digest. No OS or LLM calls here."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import threading

from sqlmodel import Session, select
from .models import Demand, Email, EmailAnalysis, EmailAccount, Reminder, Notice, Setting, as_utc, now
from .deadlines import find_deadline

DEFAULTS = {'summary_enabled': True, 'summary_time': '07:30', 'timezone': 'America/Sao_Paulo',
            'notifications_enabled': True, 'notification_details': False, 'auto_email_reminders': False}
_lock = threading.Lock()


def settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        item = db.get(Setting, f'agenda:{key}')
        if item:
            result[key] = item.value == 'true' if isinstance(default, bool) else item.value
    return result


def output(item):
    values = item.model_dump()
    for field in ('when', 'created_at'):
        if field in values:
            values[field] = as_utc(values[field])
    return values


def summary(db: Session, instant: datetime) -> dict:
    config = settings(db)
    today = as_utc(instant).astimezone(ZoneInfo(config['timezone'])).date()
    demands = db.exec(select(Demand).where(Demand.stage.not_in(('ganho', 'perdido')))).all()
    due = [d for d in demands if (d.due and d.due <= today) or (d.return_date and d.return_date <= today)]
    agenda = db.exec(select(Reminder).where(Reminder.status.in_(('pendente', 'disparado')))).all()
    reminders_today = [r for r in agenda if as_utc(r.when).astimezone(ZoneInfo(config['timezone'])).date() <= today]
    actionable = len(db.exec(select(EmailAnalysis).where(EmailAnalysis.importancia == 'acao')).all())
    return {'date': today.isoformat(), 'open': len(demands), 'due': len(due), 'reminders': len(reminders_today),
            'emails': actionable, 'demands': [{'id': d.id, 'title': d.title, 'front_id': d.front_id} for d in due[:20]],
            'body': f'{len(due)} demanda(s) para hoje ou em atraso; {len(reminders_today)} lembrete(s) e {actionable} e-mail(s) para agir.'}


def withdraw_notices(db: Session, reminder_id: int):
    for item in db.exec(select(Notice).where(Notice.reminder_id == reminder_id)).all():
        item.read = True
        if item.desktop_status == 'pendente':
            item.desktop_status = 'cancelada'
        db.add(item)


def link_demand(db: Session, demand: Demand):
    if not demand.origin_ref:
        return
    item = db.exec(select(Reminder).where(Reminder.origin_key == demand.origin_ref, Reminder.demand_id == None)).first()
    if item:
        item.demand_id = demand.id
        if demand.stage in ('ganho', 'perdido') and item.status in ('pendente', 'disparado'):
            item.status = 'concluido'
            withdraw_notices(db, item.id)
        db.add(item)


def generate(engine, instant: datetime | None = None, demo: bool = False):
    """Repeated calls/restarts are idempotent; all generated events commit together."""
    if not _lock.acquire(blocking=False):
        return
    try:
        instant = as_utc(instant or now())
        with Session(engine) as db:
            config = settings(db)
            zone = ZoneInfo(config['timezone'])
            local = instant.astimezone(zone)
            if config['auto_email_reminders'] and not demo:
                analyses = db.exec(select(EmailAnalysis).where(
                    EmailAnalysis.provisional == False, EmailAnalysis.confianca >= .9,
                    EmailAnalysis.importancia == 'acao', EmailAnalysis.prazo_iso != None)).all()
                for analysis in analyses:
                    if not analysis.trecho_prazo or analysis.correcao == 'nao_importante':
                        continue
                    key = f'email:{analysis.email_id}'
                    if db.exec(select(Reminder).where(Reminder.origin_key == key)).first():
                        continue
                    message = db.get(Email, analysis.email_id)
                    if not message or analysis.trecho_prazo not in f'{message.subject}\n{message.body_text}':
                        continue
                    reference = as_utc(message.date).astimezone(zone).date() if message.date else local.date()
                    confirmed = find_deadline(f'{message.subject}\n{message.body_text}', reference)
                    if not confirmed or confirmed.ambiguous or confirmed.iso != analysis.prazo_iso:
                        continue
                    linked = db.exec(select(Demand).where(Demand.origin_ref == key)).first()
                    if linked and linked.stage in ('ganho', 'perdido'):
                        continue
                    due = datetime.combine(analysis.prazo_iso, time(9), tzinfo=zone).astimezone(timezone.utc)
                    db.add(Reminder(text=f'Prazo do e-mail: {message.subject}'[:300], when=due, origin_key=key,
                                    demand_id=linked.id if linked else None))
                db.flush()
            for item in db.exec(select(Reminder).where(Reminder.status == 'pendente', Reminder.when <= instant)).all():
                demand = db.get(Demand, item.demand_id) if item.demand_id else None
                if demand and demand.stage in ('ganho', 'perdido'):
                    item.status = 'concluido'
                    db.add(item)
                    continue
                key = f'reminder:{item.id}:{item.revision}:{as_utc(item.when).isoformat()}'
                if not db.exec(select(Notice).where(Notice.key == key)).first():
                    db.add(Notice(key=key, kind='lembrete', title='Você tem um lembrete', body=item.text,
                                  reminder_id=item.id, demand_id=item.demand_id, created_at=instant,
                                  desktop_status='pendente' if config['notifications_enabled'] and not demo else 'silenciada'))
                item.status = 'disparado'
                db.add(item)
            if config['summary_enabled'] and not demo and local.weekday() < 5 and local.strftime('%H:%M') >= config['summary_time']:
                key = f'summary:{local.date().isoformat()}'
                if not db.exec(select(Notice).where(Notice.key == key)).first():
                    data = summary(db, instant)
                    db.add(Notice(key=key, kind='resumo', title='Seu resumo diário está pronto', body=data['body'],
                                  created_at=instant, desktop_status='pendente' if config['notifications_enabled'] else 'silenciada'))
            db.commit()
    finally:
        _lock.release()
