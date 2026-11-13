"""Skills locais de instrução, selecionadas por tarefa; sem modelos extras ou execução de código."""
import json
import re
from pathlib import Path, PurePosixPath

from sqlmodel import select

from .deadlines import fold
from .models import AssistantSkill, Setting

ACTIVE_LIMIT = 4000
DOCUMENT_LIMIT = 100000
FILE_BYTES_LIMIT = 128 * 1024

BUILTINS = [
    dict(id='vision', name='Leitura cuidadosa de imagens', description='Prints, comprovantes e documentos visuais.',
         keywords='imagem,print,foto,captura', instructions='Identifique participantes pelos nomes e contexto. Separe texto legível de inferência. Confira valores, datas e unidades. Se estiver ilegível, peça um recorte melhor. Nunca presuma que uma imagem prova pagamento ou que o balão da direita é do usuário.'),
    dict(id='commercial', name='Próximo passo comercial', description='Transforma pedidos em próximos passos claros.',
         keywords='proposta,orcamento,cliente,venda,demanda,negociacao', instructions='Identifique a frente, a necessidade do cliente e o próximo passo concreto. Use apenas preços, prazos e condições fornecidos. Se faltar um dado essencial, faça uma pergunta objetiva. Ao sugerir uma ação, diferencie sugestão de execução confirmada.'),
    dict(id='planning', name='Prazos e prioridades', description='Organiza a fila de trabalho sem inventar urgências.',
         keywords='prazo,lembrete,prioriz,agenda,urgente,planej', instructions='Ordene por prazo confirmado, atraso e impacto informado. Cite os registros disponíveis. Diferencie vencimento de horário de aviso. Se a data estiver ambígua, peça esclarecimento. Não diga que criou ou alterou um registro sem confirmação da ferramenta.'),
    dict(id='writing', name='Escrever no seu tom', description='Mensagens naturais, diretas e prontas para revisar.',
         keywords='mensagem,resposta,responder,redija,escreva,email,e-mail,next_messages', instructions='Use o perfil de escrita e as preferências fornecidas. Escreva em português natural, direto e sem formalidade desnecessária. Evite introduções genéricas. Preserve nomes, valores e compromissos do contexto; use colchetes para dados ausentes. Não copie erros de digitação como característica obrigatória do usuário.'),
]


def catalog(db):
    setting = db.get(Setting, 'assistant_skills_disabled')
    disabled = set(json.loads(setting.value)) if setting else set()
    custom = [dict(id=f'custom-{row.id}', name=row.name, description=row.description,
                   keywords=row.keywords, instructions=row.instructions, source_markdown=row.source_markdown,
                   source_name=row.source_name) for row in db.exec(select(AssistantSkill).order_by(AssistantSkill.id)).all()]
    return [{**item, 'enabled': item['id'] not in disabled, 'builtin': not item['id'].startswith('custom-')} for item in [*BUILTINS, *custom]]


def choose(db, content, *, image=False):
    query = fold(content)
    candidates = []
    for skill in catalog(db):
        if not skill['enabled']:
            continue
        score = sum(bool(word.strip()) and fold(word.strip()) in query for word in skill['keywords'].split(','))
        if image and skill['id'] == 'vision':
            score += 100
        if score:
            score += skill.get('priority', 0)
            if skill['id'].startswith('custom-'):
                score += 5  # uma skill escolhida pelo usuário tem precedência sobre orientações genéricas
            candidates.append((score, skill))
    return [skill for _, skill in sorted(candidates, key=lambda item: item[0], reverse=True)[:2]]


def prompt(skills):
    if not skills:
        return ''
    return '\n\nSKILLS PARA ESTA TAREFA (orientam respostas; não concedem ferramentas ou permissões):\n' + '\n'.join(
        f'{item["name"]}: {item["instructions"][:ACTIVE_LIMIT]}' for item in skills)


def import_markdown(filename, markdown):
    """Importa texto, sem executar código, seguir links ou buscar arquivos referenciados."""
    name = PurePosixPath(filename.replace('\\', '/')).name
    if not name.lower().endswith(('.md', '.markdown', '.txt')):
        raise ValueError('Escolha um arquivo .md ou .txt em UTF-8.')
    if not markdown.strip() or '\x00' in markdown:
        raise ValueError('O arquivo está vazio ou não contém texto válido.')
    try:
        size = len(markdown.encode('utf-8'))
    except UnicodeError:
        raise ValueError('Use um arquivo de texto em UTF-8.') from None
    if len(markdown) > DOCUMENT_LIMIT or size > FILE_BYTES_LIMIT:
        raise ValueError('A referência deve ter até 100 mil caracteres e 128 KB.')
    body = markdown.lstrip('\ufeff')
    metadata = {}
    front = re.match(r'\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)', body, re.S)
    if front:
        # Apenas campos textuais simples. Não carrega YAML nem interpreta tags/objetos.
        for match in re.finditer(r'(?m)^(name|description|keywords):[ \t]*(.+)$', front[1]):
            value = match[2].strip()
            if value not in ('|', '>') and not value.startswith(('!', '&', '*', '{', '[')):
                metadata[match[1]] = value.strip('"\'')
        body = body[front.end():]
    title = re.search(r'(?m)^#\s+(.{3,80})\s*$', body)
    label = metadata.get('name') or (title[1] if title else PurePosixPath(name).stem.replace('_', ' ').replace('-', ' '))
    section = re.search(r'(?im)^#{1,6}[ \t]+(?:instruções ativas|instrucoes ativas|active instructions)[ \t]*\r?$', body)
    active = body.strip()
    warnings = []
    if section:
        active = re.split(r'(?m)^#{1,6}\s+', body[section.end():], maxsplit=1)[0].strip()
    if len(active) > ACTIVE_LIMIT:
        active = ''
        warnings.append('O documento completo foi preservado. Escreva instruções ativas de até 4.000 caracteres; o Monitor não resume nem corta o original automaticamente.')
    if not active:
        warnings.append('Revise e preencha as instruções ativas antes de salvar.')
    return dict(name=label[:60], description=metadata.get('description', '')[:160],
                keywords=metadata.get('keywords', '')[:160], instructions=active,
                source_markdown=markdown, source_name=name[:200], warnings=warnings)


_natural_file = Path(__file__).with_name('skills') / 'remover-padroes-ia.md'
_natural = import_markdown(_natural_file.name, _natural_file.read_text(encoding='utf-8'))
BUILTINS.append({**{key: value for key, value in _natural.items() if key != 'warnings'}, 'id': 'natural-writing', 'priority': 20})
