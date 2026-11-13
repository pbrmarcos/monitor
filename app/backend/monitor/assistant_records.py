"""Registros técnicos locais sem prompts, respostas, credenciais ou imagens."""
import json
import math

from sqlmodel import Session, select

from .models import AssistantRun, now


def metrics(payload):
    result = {}
    for source, target in [('eval_count', 'output_tokens'), ('prompt_eval_count', 'input_tokens')]:
        value = payload.get(source)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[target] = value
    for source, target in [('eval_duration', 'generation_seconds'), ('prompt_eval_duration', 'prompt_seconds'),
                           ('load_duration', 'load_seconds'), ('total_duration', 'total_seconds')]:
        value = payload.get(source)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            result[target] = round(value / 1e9, 4)
    duration = payload.get('eval_duration')
    if 'output_tokens' in result and isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration > 0 and math.isfinite(duration):
        result['tokens_per_second'] = round(result['output_tokens'] / (duration / 1e9), 2)
    return result


def start(engine, conversation_id=None, *, kind='chat', model='', skills=None, detail='Gerando resposta'):
    with Session(engine) as db:
        row = AssistantRun(conversation_id=conversation_id, kind=kind, model=model, detail=detail,
                           skills=json.dumps(skills or [], ensure_ascii=False))
        db.add(row)
        db.commit()
        db.refresh(row)
        identifier = row.id
        # Retenção limitada: preserva execuções em andamento e os 200 registros recentes.
        for old in db.exec(select(AssistantRun).where(AssistantRun.status != 'running').order_by(AssistantRun.id.desc()).offset(199)).all():
            db.delete(old)
        db.commit()
        return identifier


def finish(engine, identifier, status, *, detail='', data=None, answer_id=None, skills=None, kind=None):
    with Session(engine) as db:
        row = db.get(AssistantRun, identifier)
        if row:
            row.status, row.finished_at = status, now()
            row.detail = detail
            row.metrics = json.dumps(data or {})
            row.answer_id = answer_id
            if skills is not None:
                row.skills = json.dumps(skills, ensure_ascii=False)
            if kind:
                row.kind = kind
                if kind == 'action':
                    row.model = ''
            db.add(row)
            db.commit()


def out(row):
    return {**row.model_dump(exclude={'metrics', 'skills'}), 'metrics': json.loads(row.metrics), 'skills': json.loads(row.skills)}


def reset_interrupted(engine):
    with Session(engine) as db:
        for row in db.exec(select(AssistantRun).where(AssistantRun.status == 'running')).all():
            row.status, row.finished_at, row.detail = 'interrupted', now(), 'Monitor reiniciado durante a execução'
            db.add(row)
        db.commit()
