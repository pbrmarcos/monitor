"""Regras determinísticas de importância. Rodam antes e depois da IA e prevalecem sobre ela."""
import re
from dataclasses import dataclass, field
from datetime import date
from email.utils import parseaddr

from .deadlines import find_deadline, fold

RANK = {'info': 0, 'revisar': 1, 'importante': 2, 'acao': 3}
BUDGET_SUBJECT = re.compile(r'\b(orcamento|cotacao)\b')
BUDGET_BODY = re.compile(
    r'\b(solicit\w+|gostari\w+|precis\w+|poderi\w+|pode\w*|quer\w+|envi\w+|receber|pedir|pedido|fazer|mand\w+)\b'
    r'[^.!?\n]{0,80}\b(orcamento|cotacao|proposta)\b')


@dataclass
class Context:
    today: date
    priority_senders: list[str] = field(default_factory=list)
    open_contacts: list[str] = field(default_factory=list)
    # Endereços para quem o usuário já escreveu (pasta de enviados).
    known_recipients: set[str] = field(default_factory=set)


def _squash(text: str) -> str:
    return ' '.join(fold(text).split())


def is_priority(sender: str, priority_senders: list[str]) -> bool:
    address = parseaddr(sender)[1].lower()
    return any(item and (item == address or (item.startswith('@') and address.endswith(item)) or
                         ('@' not in item and address.endswith('@' + item)))
               for item in (value.strip().lower() for value in priority_senders))


def is_open_client(sender: str, open_contacts: list[str]) -> bool:
    name, address = parseaddr(sender)
    address, name = address.lower(), fold(name).strip()
    for contact in open_contacts:
        folded = fold(contact)
        if (address and address in folded) or (len(name) > 3 and name in folded):
            return True
    return False


def decide(sender: str, subject: str, body: str, bulk: bool, ai: dict | None, context: Context) -> dict:
    """Combina a resposta da IA (ou a ausência dela) com as regras e devolve a análise final."""
    text = f'{subject}\n{body}'
    result = dict(ai) if ai else {
        'categoria': 'publicidade' if bulk else 'outro', 'importancia': 'revisar',
        'motivo': 'Aguardando análise da IA.', 'resumo': ' '.join(body.split())[:240],
        'acao_sugerida': None, 'prazo_texto': None, 'prazo_iso': None, 'trecho_prazo': None,
        'criar_demanda': False, 'confianca': 0.0,
    }
    reasons: list[str] = []
    priority = is_priority(sender, context.priority_senders)
    client = is_open_client(sender, context.open_contacts)

    found = find_deadline(text, context.today)
    ambiguous = bool(found and found.ambiguous)
    if found:
        result.update(prazo_texto=found.text, prazo_iso=found.iso, trecho_prazo=found.snippet)
    elif result.get('prazo_texto') or result.get('prazo_iso'):
        # Prazo vindo só da IA precisa de data e de um trecho literal da mensagem.
        excerpt = result.get('trecho_prazo')
        literal = bool(excerpt) and _squash(excerpt) in _squash(text)
        if not literal:
            result['trecho_prazo'] = None
        if not (result.get('prazo_iso') and literal):
            result['prazo_iso'] = None
            ambiguous = True

    if result['categoria'] == 'publicidade':
        result['importancia'] = 'info'
        reasons.append('Publicidade fica como informativo.')
    if ai and (result['confianca'] < 0.6 or ambiguous):
        result['importancia'] = 'revisar'
        reasons.append('Data ambígua, confira o prazo.' if ambiguous else 'Confiança baixa da IA.')
    elif ambiguous:
        reasons.append('Data ambígua, confira o prazo.')
    if (priority or client) and RANK[result['importancia']] < RANK['importante']:
        result['importancia'] = 'importante'
        reasons.append('Remetente prioritário.' if priority else 'Cliente com demanda aberta.')
    if (not bulk and parseaddr(sender)[1].lower() in context.known_recipients
            and RANK[result['importancia']] < RANK['importante']):
        result['importancia'] = 'importante'
        reasons.append('Você já escreveu para este remetente.')
    folded_subject, folded_body = fold(subject), fold(body)
    if not bulk and (BUDGET_SUBJECT.search(folded_subject) or BUDGET_BODY.search(folded_body)):
        result.update(importancia='acao', criar_demanda=True)
        if result['categoria'] in ('outro', 'informativo', 'publicidade'):
            result['categoria'] = 'orcamento'
        reasons.append('Pedido explícito de orçamento.')
    if found and not found.ambiguous and (not bulk or priority):
        result.update(importancia='acao', criar_demanda=True)
        reasons.append('Prazo com data.')
    if reasons:
        base = result['motivo'].strip()
        result['motivo'] = f"{base} {' '.join(f'Regra: {reason}' for reason in reasons)}".strip()[:500]
    return result
