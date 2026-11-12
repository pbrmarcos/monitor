from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from . import reminders
from .models import Demand, Reminder, Notice, Setting, as_utc, now


class ReminderInput(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    when: datetime
    demand_id: int | None = Field(default=None, gt=0)

    @field_validator('text')
    @classmethod
    def title(cls, value):
        if not value.strip():
            raise ValueError('Informe o texto do lembrete.')
        return value.strip()

    @field_validator('when')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError('Informe data, hora e fuso horário.')
        return value.astimezone(timezone.utc)


class AgendaSettings(BaseModel):
    summary_enabled: bool = True
    summary_time: str = Field(default='07:30', pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    timezone: str = 'America/Sao_Paulo'
    notifications_enabled: bool = True
    notification_details: bool = False
    auto_email_reminders: bool = False

    @field_validator('timezone')
    @classmethod
    def zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Escolha um fuso horário válido.') from None
        return value


def router(engine, session, demo):
    api = APIRouter()

    @api.get('/agenda/settings')
    def config(db: Session = Depends(session)):
        return reminders.settings(db)

    @api.put('/agenda/settings')
    def save_config(payload: AgendaSettings, db: Session = Depends(session)):
        for key, value in payload.model_dump().items():
            db.merge(Setting(key=f'agenda:{key}', value=str(value).lower() if isinstance(value, bool) else value))
        if not payload.notifications_enabled:
            for item in db.exec(select(Notice).where(Notice.desktop_status == 'pendente')).all():
                item.desktop_status = 'silenciada'
                db.add(item)
        db.commit()
        return reminders.settings(db)

    @api.get('/reminders')
    def list_reminders(db: Session = Depends(session)):
        return [reminders.output(item) for item in db.exec(select(Reminder).order_by(Reminder.when)).all()]

    def validate_demand(payload, db):
        if payload.demand_id and not db.get(Demand, payload.demand_id):
            raise HTTPException(404, 'Demanda não encontrada.')

    @api.post('/reminders', status_code=201)
    def create(payload: ReminderInput, db: Session = Depends(session)):
        validate_demand(payload, db)
        item = Reminder(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return reminders.output(item)

    def get(identifier, db):
        item = db.get(Reminder, identifier)
        if not item:
            raise HTTPException(404, 'Lembrete não encontrado.')
        return item

    @api.put('/reminders/{identifier}')
    def update(identifier: int, payload: ReminderInput, db: Session = Depends(session)):
        validate_demand(payload, db)
        item = get(identifier, db)
        reminders.withdraw_notices(db, identifier)
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        item.status = 'pendente'
        item.revision += 1
        db.add(item)
        db.commit()
        db.refresh(item)
        return reminders.output(item)

    @api.post('/reminders/{identifier}/{action}')
    def resolve(identifier: int, action: str, db: Session = Depends(session)):
        if action not in ('complete', 'cancel'):
            raise HTTPException(404, 'Ação não encontrada.')
        item = get(identifier, db)
        item.status = 'concluido' if action == 'complete' else 'cancelado'
        reminders.withdraw_notices(db, identifier)
        db.add(item)
        db.commit()
        db.refresh(item)
        return reminders.output(item)

    @api.get('/agenda/summary')
    def summary(db: Session = Depends(session)):
        return reminders.summary(db, now())

    @api.get('/agenda/alert')
    def alert(db: Session = Depends(session)):
        return {'active': db.exec(select(Notice.id).where(Notice.read == False)).first() is not None}

    @api.get('/notifications')
    def notices(db: Session = Depends(session)):
        return [reminders.output(n) for n in db.exec(select(Notice).order_by(Notice.id.desc()).limit(100)).all()]

    @api.post('/notifications/{identifier}/read', status_code=204)
    def read(identifier: int, db: Session = Depends(session)):
        item = db.get(Notice, identifier)
        if not item:
            raise HTTPException(404, 'Aviso não encontrado.')
        item.read = True
        if item.desktop_status == 'pendente':
            item.desktop_status = 'silenciada'
        db.add(item)
        db.commit()

    @api.get('/notifications/desktop')
    def delivery(db: Session = Depends(session)):
        config = reminders.settings(db)
        if demo or not config['notifications_enabled']:
            return []
        items = db.exec(select(Notice).where(Notice.desktop_status == 'pendente', Notice.read == False).order_by(Notice.id).limit(5)).all()
        return [{'id': n.id, 'title': n.title, 'body': n.body if config['notification_details'] else 'Abra o Monitor para conferir os detalhes.',
                 'demand_id': n.demand_id} for n in items]

    @api.post('/notifications/{identifier}/delivered', status_code=204)
    def delivered(identifier: int, db: Session = Depends(session)):
        item = db.get(Notice, identifier)
        if item and item.desktop_status == 'pendente':
            item.desktop_status = 'enviada'
            db.add(item)
            db.commit()

    return api
