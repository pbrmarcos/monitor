"""Leitura determinística de prazos escritos em português."""
import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = {'segunda': 0, 'terca': 1, 'quarta': 2, 'quinta': 3, 'sexta': 4, 'sabado': 5, 'domingo': 6}
MONTHS = {name: index + 1 for index, name in enumerate(
    ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'])}

EXPRESSION = re.compile(rf'''
    \b(?P<d>\d{{1,2}})/(?P<m>\d{{1,2}})(?:/(?P<y>\d{{4}}|\d{{2}}))?\b
  | \b(?:dia\s+)?(?P<d2>\d{{1,2}})\s+de\s+(?P<mon>{'|'.join(MONTHS)})(?:\s+de\s+(?P<y2>\d{{4}}))?\b
  | \bdia\s+(?P<d3>\d{{1,2}})\b
  | \b(?P<dep>depois\s+de\s+amanha)\b
  | \b(?P<ama>amanha)\b
  | \b(?P<hoje>hoje)\b
  | \b(?:proxima\s+)?(?P<wd>{'|'.join(WEEKDAYS)})(?:-feira)?
      (?!\s+(?:opcao|vez|parte|etapa|fase|via|parcela|versao|reuniao|proposta))
      (?P<wdnext>\s+(?:que\s+vem|da\s+semana\s+que\s+vem|da\s+proxima\s+semana))?
  | \b(?P<sem>semana\s+que\s+vem|proxima\s+semana)\b
  | \b(?P<fim>(?:fim|final)\s+d[oe]\s+mes)\b
''', re.X)
CUE = re.compile(r'\b(ate|prazo|para|entreg\w+|venc\w+|limite|preciso|precisamos|necessito|retorn\w+|respond\w+|envi\w+)\b[^.!?\n]{0,40}$')


@dataclass
class Deadline:
    text: str
    iso: date | None
    snippet: str
    ambiguous: bool = False


def fold(text: str) -> str:
    """Minúsculas sem acento, preservando a posição de cada caractere."""
    result = []
    for char in unicodedata.normalize('NFC', text):
        base = unicodedata.normalize('NFD', char.lower())
        result.append(base[0] if base else ' ')
    return ''.join(result)


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve(match: re.Match, today: date) -> tuple[date | None, bool]:
    group = match.groupdict()
    if group['d'] or group['d2']:
        day = int(group['d'] or group['d2'])
        month = int(group['m']) if group['m'] else MONTHS[group['mon']]
        year = group['y'] or group['y2']
        if year:
            return _safe(int(year) + (2000 if len(year) == 2 else 0), month, day), False
        value = _safe(today.year, month, day)
        if value and value < today - timedelta(days=1):
            value = _safe(today.year + 1, month, day)
        return value, False
    if group['d3']:
        day = int(group['d3'])
        year, month = today.year, today.month
        if day < today.day:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return _safe(year, month, day), False
    if group['dep']:
        return today + timedelta(days=2), False
    if group['ama']:
        return today + timedelta(days=1), False
    if group['hoje']:
        return today, False
    if group['wd']:
        target = WEEKDAYS[group['wd']]
        if group['wdnext']:
            return today + timedelta(days=7 - today.weekday() + target), False
        return today + timedelta(days=(target - today.weekday()) % 7 or 7), False
    if group['sem']:
        # Sem dia definido: a data fica em aberto e a mensagem vai para revisão.
        return None, True
    last = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, last), False


def _snippet(original: str, start: int, end: int) -> str:
    left = max(original.rfind(mark, 0, start) for mark in '.!?\n') + 1
    rights = [index for index in (original.find(mark, end) for mark in '.!?\n') if index != -1]
    right = min(rights) + 1 if rights else len(original)
    return ' '.join(original[left:right].split())[:200]


def _build(original: str, match: re.Match, today: date) -> Deadline | None:
    iso, ambiguous = _resolve(match, today)
    if not iso and not ambiguous:
        return None
    return Deadline(original[match.start():match.end()].strip(), iso, _snippet(original, match.start(), match.end()), ambiguous)


def parse_expression(text: str, today: date) -> Deadline | None:
    """Interpreta a primeira expressão de data do texto, sem exigir contexto."""
    original = unicodedata.normalize('NFC', text)
    for match in EXPRESSION.finditer(fold(original)):
        if deadline := _build(original, match, today):
            return deadline
    return None


def find_deadline(text: str, today: date) -> Deadline | None:
    """Procura um prazo: expressão de data precedida, na mesma frase, por um termo de prazo."""
    original = unicodedata.normalize('NFC', text)
    folded = fold(original)
    fallback = None
    for match in EXPRESSION.finditer(folded):
        if not CUE.search(folded[max(0, match.start() - 60):match.start()]):
            continue
        deadline = _build(original, match, today)
        if deadline and not deadline.ambiguous:
            return deadline
        fallback = fallback or deadline
    return fallback
