"""Ferramentas do chat: pedidos diretos, argumentos verificáveis e resultado do banco.

Nenhum texto produzido pelo modelo ou coletado de e-mails autoriza uma operação.
"""
import json
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text as sql_text
from sqlmodel import Session, select

from . import gcal, prefs, reminders
from .agenda_api import ReminderInput
from .deadlines import EXPRESSION, fold, parse_expression
from .models import AssistantAction, ChatTurn, Conversation, Demand, Event, Reminder, ReminderCalendarLink, as_utc, now
from .secrets_store import SecretError

CREATE = r'(?:crie|cria|criar|criasse|adicione|adiciona|adicionar|agende|agenda|agendar|marque|marcar|registre|registrar|anote|anotar|faca|fazer)'
GOOGLE = r'\b(?:na|no|para|em)\s+(?:(?:a|minha|meu)\s+)?(?:agenda(?:\s+do)?\s+)?google\b|\bgoogle agenda\b'
CLOCK = re.compile(r'\b(\d{1,2})(?::(\d{2})|h(?:(\d{2})\b)?|\s+horas?\b)|\bas\s+(\d{1,2})(?![:\d])\b')
ISO = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')


class NeedInfo(Exception):
    pass


def command(content):
    value = fold(content.strip())
    prefix = r'^(?:por favor[, ]+)?(?:(?:voce )?(?:pode|poderia|consegue)\s+|(?:eu )?(?:quero|preciso|gostaria)(?: que(?: voce)?| de(?: voce)?)?\s+)?'
    match = re.match(prefix + CREATE + r'\s+(?:(?:um|uma|o|a|esse|este|essa|esta)\s+)?(?P<noun>lembrete|compromisso|evento|consulta|reuniao|demanda|tarefa|oportunidade)\b', value)
    if match:
        noun = match['noun']
        rest = content.strip()[match.end():].strip(' :,-')
        if noun in ('consulta', 'reuniao'):
            rest = ('Consulta' if noun == 'consulta' else 'Reunião') + ' ' + rest
        return ('create_demand' if noun in ('demanda', 'tarefa', 'oportunidade') else 'create_reminder'), rest
    match = re.match(prefix + r'(?:me lembre|lembre-me|me avise|me lembrar)\b(?:\s+de)?', value)
    if match:
        return 'create_reminder', content.strip()[match.end():].strip(' :,-')
    match = re.match(prefix + r'(?P<verb>reagende|reagendar|remarque|remarcar|adie|adiar|altere|alterar|mude|mudar|mova|mover|conclua|concluir|complete|completar|cancele|cancelar)\b', value)
    if match:
        if re.search(r'\blembrete\b|\[l\d+\]', value):
            operation = 'complete' if match['verb'].startswith(('concl', 'complet')) else 'cancel' if match['verb'].startswith('cancel') else 'update'
            return operation + '_reminder', content.strip()[match.end():].strip()
        if re.search(r'\bdemanda\b|\[d\d+\]', value):
            return 'update_demand', content.strip()[match.end():].strip()
    return None


def schedule_parts(content, local):
    value, fields, spans = fold(content), {}, []
    iso = list(ISO.finditer(value))
    expressions = list(EXPRESSION.finditer(value)) if not iso else []
    if len(iso) + len(expressions) > 1:
        raise NeedInfo('Encontrei mais de uma data. Envie um compromisso por vez, com a data desejada.')
    if iso:
        try:
            fields['day'] = date.fromisoformat(iso[0][0]).isoformat()
        except ValueError:
            raise NeedInfo('Essa data não existe. Informe uma data válida, como 08/12/2026.') from None
        spans.append(iso[0].span())
    elif expressions:
        parsed = parse_expression(content, local.date())
        if not parsed or parsed.ambiguous or not parsed.iso:
            raise NeedInfo('Qual é a data exata? Use, por exemplo, 08/12/2026 ou amanhã.')
        fields['day'] = parsed.iso.isoformat()
        spans.append(expressions[0].span())
    duration_match = re.search(r'\b(?:por|duracao(?: de)?)\s+(\d+)\s*(minutos?|min|horas?)\b', value)
    relative_match = re.search(r'\bdaqui (?:a )?(\d+)\s*(minutos?|min|horas?)\b', value)
    clock_text = list(value)
    for match in (duration_match, relative_match):
        if match:
            clock_text[match.start():match.end()] = ' ' * len(match[0])
    clocks = list(CLOCK.finditer(''.join(clock_text)))
    if len(clocks) > 1:
        raise NeedInfo('Informe apenas o horário de início. Para a duração, use “por 45 minutos”, por exemplo.')
    if clocks:
        match = clocks[0]
        hour, minute = int(match[1] or match[4]), int(match[2] or match[3] or 0)
        if hour > 23 or minute > 59:
            raise NeedInfo('Esse horário não é válido. Informe um horário de 00:00 a 23:59.')
        fields['clock'] = f'{hour:02}:{minute:02}'
        spans.append(match.span())
    relative = re.search(r'\bdaqui (?:a )?(\d+)\s*(minutos?|min|horas?)\b', value)
    if relative:
        minutes = int(relative[1]) * (60 if relative[2].startswith('hora') else 1)
        if not 1 <= minutes <= 60 * 24 * 30:
            raise NeedInfo('Use um intervalo entre um minuto e 30 dias ou informe uma data e um horário.')
        instant = local + timedelta(minutes=minutes)
        fields.update(day=instant.date().isoformat(), clock=instant.strftime('%H:%M'))
        spans.append(relative.span())
    duration = re.search(r'\b(?:por|duracao(?: de)?)\s+(\d+)\s*(minutos?|min|horas?)\b', value)
    if duration:
        minutes = int(duration[1]) * (60 if duration[2].startswith('hora') else 1)
        if not 1 <= minutes <= 1440:
            raise NeedInfo('A duração deve ficar entre um minuto e 24 horas.')
        fields['duration'] = minutes
        spans.append(duration.span())
    remaining = list(content)
    for start, end in spans:
        remaining[start:end] = ' ' * (end - start)
    return fields, ''.join(remaining)


def extract(db, content, rest, kind, base, front_id, local):
    args = dict(base)
    fields, title = schedule_parts(rest, local)
    args.update(fields)
    value = fold(content)
    if re.search(GOOGLE, value):
        args['google'] = True
    if re.search(r'\b(?:aqui no sistema|no monitor|apenas local|so aqui|somente no sistema)\b', value):
        args['google'] = False
    if kind.endswith('demand'):
        fronts = prefs.front_names(db)
        matches = [(identifier, name) for identifier, name in fronts.items() if re.search(r'(?<!\w)' + re.escape(fold(name)) + r'(?!\w)', value)]
        if len(matches) > 1:
            raise NeedInfo('Qual frente deve receber esta demanda? Envie apenas uma por vez.')
        if matches:
            args['front_id'] = matches[0][0]
            title = re.sub(re.escape(matches[0][1]), '', title, flags=re.I)
        elif front_id and not args.get('front_id'):
            args['front_id'] = front_id
    if not kind.startswith('create'):
        letter = 'l' if kind.endswith('reminder') else 'd'
        noun = 'lembrete' if letter == 'l' else 'demanda'
        ids = re.findall(r'\[' + letter + r'(\d+)\]|\b' + noun + r'\s*#?\s*(\d+)\b', value)
        identifiers = {int(a or b) for a, b in ids}
        if len(identifiers) > 1:
            raise NeedInfo('Envie um único identificador por vez.')
        if identifiers:
            args['id'] = identifiers.pop()
        if kind == 'update_demand':
            stages = {'proposta enviada': 'proposta_enviada', 'preparar proposta': 'preparar_proposta', 'qualificacao': 'qualificacao', 'acompanhar': 'acompanhar', 'ganho': 'ganho', 'ganha': 'ganho', 'perdido': 'perdido', 'perdida': 'perdido', 'novo': 'novo'}
            found = {stage for label, stage in stages.items() if re.search(r'\b' + label + r'\b', value)}
            if len(found) > 1:
                raise NeedInfo('Qual é a etapa final desejada para a demanda?')
            if found:
                args['stage'] = found.pop()
            if re.search(r'prioridade (?:alta|normal)', value):
                args['priority'] = re.search(r'prioridade (alta|normal)', value)[1]
    elif not args.get('title'):
        # Remove apenas os trechos de destino; preserva a grafia do título original.
        for match in reversed(list(re.finditer(GOOGLE, fold(title)))):
            title = title[:match.start()] + title[match.end():]
        title = re.sub(r'^(?:(?:pra|para) mim\b|de\b|para\b|sobre\b)\s*', '', title.strip(), flags=re.I)
        title = re.sub(r'\b(?:aqui no sistema|no Monitor|na frente|para a frente)\b', '', title, flags=re.I)
        title = re.sub(r'(?:\b(?:dia|em|no dia|para|pra|as|às|até|ate|da|na|do|de)\b[\s,:-]*)+$', '', title.strip(), flags=re.I)
        title = ' '.join(title.split()).strip(' ,:.-')
        if title and fold(title) not in ('aqui', 'isso', 'esse', 'este', 'o mesmo', 'um lembrete'):
            args['title'] = title
    return args


def reply_fits(content, arguments):
    value = fold(content.strip())
    if not value or value in ('sim', 'nao', 'ok', 'certo', 'pode', 'valeu') or '?' in value or re.match(r'^(?:o que|como|por que|quem|quais|obrigad\w*|resuma|explique|abra|feche|mostre|envie|apague|exclua|reinicie|liste)\b', value):
        return False
    if ISO.search(value) or EXPRESSION.search(value) or CLOCK.search(value) or re.search(r'\[[ld]\d+\]', value):
        return True
    if re.search(r'prioridade (alta|normal)|frente|\b(?:ganho|perdido|acompanhar)\b', value):
        return True
    return not arguments.get('title') and len(content) <= 300


def instant_for(args, zone, local):
    if not args.get('day') or not args.get('clock'):
        if not args.get('day') and not args.get('clock'):
            raise NeedInfo('Quais são a data e o horário do lembrete?')
        missing = 'data' if not args.get('day') else 'horário'
        raise NeedInfo(f'Qual é a {missing}?' if missing == 'data' else f'Qual é o {missing}?')
    value = datetime.combine(date.fromisoformat(args['day']), time.fromisoformat(args['clock']), tzinfo=zone)
    if value <= local:
        raise NeedInfo('Essa data e horário já passaram. Qual data e horário devo usar?')
    if value.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != value.replace(tzinfo=None):
        raise NeedInfo('Esse horário não existe no fuso configurado devido à mudança de horário. Escolha outro horário.')
    return value.astimezone(timezone.utc)


def execute(db, kind, args, local, zone):
    if kind == 'create_reminder':
        when = instant_for(args, zone, local)
        if not args.get('title'):
            raise NeedInfo('Qual é o texto do lembrete?')
        if len(args['title']) > 300:
            raise NeedInfo('Resuma o texto do lembrete em até 300 caracteres.')
        data = ReminderInput(text=args['title'], when=when)
        item = db.exec(select(Reminder).where(Reminder.text == data.text, Reminder.when == when, Reminder.status.in_(('pendente', 'disparado')))).first()
        duplicate = item is not None
        if not item:
            item = Reminder(**data.model_dump())
            db.add(item)
            db.flush()
        if args.get('google'):
            link = db.get(ReminderCalendarLink, item.id) or ReminderCalendarLink(reminder_id=item.id, event_id=uuid.uuid4().hex)
            if args.get('duration'):
                link.duration_minutes = args['duration']
            db.add(link)
        return {'kind': 'reminder', 'id': item.id, 'operation': 'existing' if duplicate else 'created', 'text': item.text, 'when': when.isoformat(), 'timezone': str(zone)}
    if kind.endswith('reminder'):
        if not args.get('id'):
            raise NeedInfo('Qual lembrete? Informe o identificador, por exemplo [L3].')
        item = db.get(Reminder, args['id'])
        if not item:
            raise NeedInfo('Não encontrei esse lembrete. Confira o identificador na tela Lembretes.')
        if kind == 'update_reminder':
            item.when = instant_for(args, zone, local)
            item.revision += 1
            item.status = 'pendente'
        else:
            item.status = 'concluido' if kind == 'complete_reminder' else 'cancelado'
        reminders.withdraw_notices(db, item.id)
        db.add(item)
        return {'kind': 'reminder', 'id': item.id, 'operation': kind.split('_')[0], 'text': item.text, 'when': as_utc(item.when).isoformat(), 'timezone': str(zone)}
    if kind == 'create_demand':
        if not args.get('title'):
            raise NeedInfo('Qual é o título da demanda?')
        if not args.get('front_id'):
            raise NeedInfo('Qual frente deve receber a demanda? ' + ', '.join(prefs.front_names(db).values()) + '.')
        from .main import DemandInput
        data = DemandInput(title=args['title'][:200], front_id=args['front_id'], due=args.get('day'))
        item = db.exec(select(Demand).where(Demand.title == data.title, Demand.front_id == data.front_id, Demand.due == data.due, Demand.stage.not_in(('ganho', 'perdido')))).first()
        duplicate = item is not None
        if not item:
            item = Demand(**data.model_dump(), created_by='assistente')
            db.add(item)
            db.flush()
            db.add(Event(demand_id=item.id, description='Demanda criada pelo assistente por pedido direto do usuário.'))
        return {'kind': 'demand', 'id': item.id, 'operation': 'existing' if duplicate else 'created', 'text': item.title}
    if not args.get('id'):
        raise NeedInfo('Qual demanda? Informe o identificador, por exemplo [D3].')
    item = db.get(Demand, args['id'])
    if not item:
        raise NeedInfo('Não encontrei essa demanda. Confira o identificador na tela Demandas.')
    if not any(key in args for key in ('stage', 'priority', 'day')):
        raise NeedInfo('Informe a etapa, a prioridade (alta ou normal) ou a data desejada para a demanda.')
    if args.get('stage') == 'acompanhar' and not args.get('day') and not item.return_date:
        raise NeedInfo('Qual é a data de retorno para colocar a demanda em Acompanhar?')
    if args.get('stage'):
        item.stage = args['stage']
    if args.get('priority'):
        item.priority = args['priority']
    if args.get('day'):
        if item.stage == 'acompanhar':
            item.return_date = date.fromisoformat(args['day'])
        else:
            item.due = date.fromisoformat(args['day'])
    db.add(item)
    db.add(Event(demand_id=item.id, description='Demanda atualizada pelo assistente por pedido direto do usuário.'))
    if item.stage in ('ganho', 'perdido'):
        for reminder in db.exec(select(Reminder).where(Reminder.demand_id == item.id, Reminder.status.in_(('pendente', 'disparado')))).all():
            reminder.status = 'concluido'
            reminders.withdraw_notices(db, reminder.id)
            db.add(reminder)
    return {'kind': 'demand', 'id': item.id, 'operation': 'updated', 'text': item.title}


def describe(result):
    label = '[L' if result['kind'] == 'reminder' else '[D'
    verbs = {'created': 'Criado', 'existing': 'Já existe', 'update': 'Reagendado', 'complete': 'Concluído', 'cancel': 'Cancelado', 'updated': 'Atualizado'}
    message = f"{verbs[result['operation']]} {label}{result['id']}]: {result['text']}."
    if result.get('when'):
        local = datetime.fromisoformat(result['when']).astimezone(ZoneInfo(result['timezone']))
        message += f" Data: {local:%d/%m/%Y às %H:%M} ({result['timezone']})."
    return message


def handle(engine, conversation_id, question_id, content, *, front_id=None, vault=None, demo=False):
    """Retorna None para conversa comum; ações e esclarecimentos têm resposta do executor."""
    with Session(engine) as db:
        db.execute(sql_text('BEGIN IMMEDIATE'))
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return {'text': 'A conversa foi excluída.', 'action': None}
        previous = db.exec(select(AssistantAction).where(AssistantAction.question_id == question_id)).first()
        if previous:
            return json.loads(previous.result)
        zone = ZoneInfo(reminders.settings(db)['timezone'])
        local = now().astimezone(zone)
        draft = db.exec(select(AssistantAction).where(AssistantAction.conversation_id == conversation_id, AssistantAction.status == 'pending').order_by(AssistantAction.id.desc())).first()
        if draft and as_utc(draft.created_at) < now() - timedelta(days=1):
            draft.status = 'expired'
            db.add(draft)
            draft = None
        parsed, base = command(content), {}
        if parsed:
            kind, rest = parsed
            referential = bool(re.search(r'\b(?:aqui|esse|este|mesmo)\b', fold(content)))
            if referential:
                try:
                    referential = not extract(db, content, rest, kind, {}, front_id, local).get('title')
                except NeedInfo:
                    referential = False
            if draft and draft.kind == kind and referential:
                base = json.loads(draft.arguments)
            elif referential:
                turns = db.exec(select(ChatTurn).where(ChatTurn.conversation_id == conversation_id, ChatTurn.id < question_id, ChatTurn.role == 'user').order_by(ChatTurn.id.desc()).limit(6)).all()
                for turn in turns:
                    old = command(turn.content)
                    if old and old[0] == kind:
                        try:
                            base = extract(db, turn.content, old[1], kind, {}, front_id, local)
                        except NeedInfo:
                            pass
                        break
        elif draft and fold(content.strip()) in ('cancele', 'cancelar', 'esqueca', 'cancele isso'):
            draft.status = 'cancelled'
            db.add(draft)
            answer = ChatTurn(conversation_id=conversation_id, role='action', content='Pedido pendente cancelado. Nenhum registro foi criado.')
            db.add(answer)
            db.commit()
            return {'text': answer.content, 'action': None}
        elif draft and (reply_fits(content, json.loads(draft.arguments)) or
                        draft.kind.endswith('demand') and not json.loads(draft.arguments).get('front_id') and
                        fold(content.strip()) in [fold(name) for name in prefs.front_names(db).values()]):
            kind, rest, base = draft.kind, content, json.loads(draft.arguments)
        else:
            return None
        action = AssistantAction(conversation_id=conversation_id, question_id=question_id, kind=kind, created_at=now())
        result, args = None, base
        try:
            if re.search(r'\be\s+' + CREATE + r'\b', fold(rest)):
                raise NeedInfo('Envie uma ação por mensagem para eu registrar os dados corretamente.')
            args = extract(db, content, rest, kind, base, front_id, local)
            result = execute(db, kind, args, local, zone)
            action.status = 'done'
            message = describe(result)
        except NeedInfo as error:
            message = str(error)
        action.arguments = json.dumps(args, ensure_ascii=False)
        if draft:
            draft.status = 'superseded'
            db.add(draft)
        answer = ChatTurn(conversation_id=conversation_id, role='action', content=message)
        db.add(answer)
        db.flush()
        action.answer_id = answer.id
        output = {'text': message, 'action': result}
        action.result = json.dumps(output, ensure_ascii=False)
        db.add(action)
        conversation.updated_at = now()
        db.add(conversation)
        db.commit()
        action_id, answer_id = action.id, answer.id
        wants_google = result and result['kind'] == 'reminder' and db.get(ReminderCalendarLink, result['id']) is not None
    if result:
        # A chamada externa acontece após o commit local, nunca com a transação aberta.
        connected = False
        try:
            connected = bool(vault and vault.get(gcal.TOKEN_REF))
            if not demo and connected and wants_google:
                gcal.sync(engine, vault, reminder_id=result['id'])
        except SecretError:
            pass  # o registro local continua válido mesmo sem acesso ao cofre
        with Session(engine) as db:
            if result['kind'] == 'reminder' and (link := db.get(ReminderCalendarLink, result['id'])):
                if demo:
                    message += ' Modo de demonstração: nenhum evento foi enviado ao Google.'
                elif result['operation'] == 'cancel':
                    message += ' O cancelamento no Google ainda está pendente de sincronização.'
                elif link.fingerprint == gcal._fingerprint(gcal.reminder_event_for(db.get(Reminder, result['id']), link, result['timezone'])):
                    message += f' Evento sincronizado com o Google Agenda; duração de {link.duration_minutes} minutos.'
                elif not connected:
                    message += ' Salvo no Monitor. O envio ao Google está pendente: conecte a Agenda Google em Configurações.'
                else:
                    message += ' Salvo no Monitor. O Google ainda não confirmou o evento; a sincronização tentará novamente.'
                if not link.fingerprint and not demo:
                    message += f' Duração planejada: {link.duration_minutes} minutos.'
            output = {'text': message, 'action': result}
            if row := db.get(ChatTurn, answer_id):
                row.content = message
                db.add(row)
            if row := db.get(AssistantAction, action_id):
                row.result = json.dumps(output, ensure_ascii=False)
                db.add(row)
            db.commit()
    return output
