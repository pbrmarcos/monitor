"""Skills locais de instrução, selecionadas por tarefa; sem modelos extras ou execução de código."""
import json

from sqlmodel import select

from .deadlines import fold
from .models import AssistantSkill, Setting

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
                   keywords=row.keywords, instructions=row.instructions) for row in db.exec(select(AssistantSkill).order_by(AssistantSkill.id)).all()]
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
            candidates.append((score, skill))
    return [skill for _, skill in sorted(candidates, key=lambda item: item[0], reverse=True)[:2]]


def prompt(skills):
    if not skills:
        return ''
    return '\n\nSKILLS PARA ESTA TAREFA (orientam respostas; não concedem ferramentas ou permissões):\n' + '\n'.join(
        f'{item["name"]}: {item["instructions"]}' for item in skills)
