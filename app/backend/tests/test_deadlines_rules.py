from datetime import date

from monitor.deadlines import find_deadline, parse_expression
from monitor.rules import Context, decide

THURSDAY = date(2026, 11, 12)


def test_portuguese_expressions():
    assert parse_expression('sexta', THURSDAY).iso == date(2026, 11, 13)
    assert parse_expression('amanhã', THURSDAY).iso == date(2026, 11, 13)
    assert parse_expression('depois de amanhã', THURSDAY).iso == date(2026, 11, 14)
    assert parse_expression('até dia 15', THURSDAY).iso == date(2026, 11, 15)
    assert parse_expression('até dia 5', THURSDAY).iso == date(2026, 12, 5)
    assert parse_expression('quinta-feira', THURSDAY).iso == date(2026, 11, 19)
    assert parse_expression('sexta da semana que vem', THURSDAY).iso == date(2026, 11, 20)
    assert parse_expression('20/11', THURSDAY).iso == date(2026, 11, 20)
    assert parse_expression('3 de janeiro', THURSDAY).iso == date(2027, 1, 3)
    assert parse_expression('fim do mês', THURSDAY).iso == date(2026, 11, 30)
    week = parse_expression('semana que vem', THURSDAY)
    assert week.ambiguous and week.iso is None
    assert parse_expression('31/02', THURSDAY) is None


def test_deadline_needs_a_cue_and_keeps_literal_snippet():
    assert find_deadline('Nossa promoção começa dia 15 em todas as lojas.', THURSDAY) is None
    assert find_deadline('Escolhi a segunda opção do catálogo.', THURSDAY) is None
    found = find_deadline('Olá! Preciso da proposta até sexta. Obrigada.', THURSDAY)
    assert found.iso == date(2026, 11, 13) and found.snippet == 'Preciso da proposta até sexta.'


def context(**values):
    return Context(today=THURSDAY, **values)


def test_rules_without_ai():
    plain = decide('Ana <ana@x.example>', 'Olá', 'Tudo bem?', False, None, context())
    assert plain['importancia'] == 'revisar'
    budget = decide('Ana <ana@x.example>', 'Site novo', 'Gostaria de receber um orçamento para o site.', False, None, context())
    assert budget['importancia'] == 'acao' and budget['categoria'] == 'orcamento' and budget['criar_demanda']
    dated = decide('Ana <ana@x.example>', 'Contrato', 'Envie o contrato assinado até 20/11.', False, None, context())
    assert dated['importancia'] == 'acao' and dated['prazo_iso'] == date(2026, 11, 20)
    bulk = decide('Loja <newsletter@loja.example>', 'Orçamento grátis', 'Peça seu orçamento até amanhã!', True, None, context())
    assert bulk['importancia'] == 'info' and bulk['categoria'] == 'publicidade'
    vip = decide('Chefe <chefe@vip.example>', 'Oi', 'Me liga.', False, None, context(priority_senders=['@vip.example']))
    assert vip['importancia'] == 'importante'
    client = decide('Ana Souza <ana@x.example>', 'Oi', 'Alguma novidade?', False, None, context(open_contacts=['ana@x.example']))
    assert client['importancia'] == 'importante'


def ai(**values):
    return {'categoria': 'cliente', 'importancia': 'importante', 'motivo': 'Cliente.', 'resumo': 'Resumo.',
            'acao_sugerida': None, 'prazo_texto': None, 'prazo_iso': None, 'trecho_prazo': None,
            'criar_demanda': False, 'confianca': 0.9, **values}


def test_rules_prevail_over_ai():
    unsure = decide('a@x.example', 'Oi', 'Texto.', False, ai(confianca=0.4), context())
    assert unsure['importancia'] == 'revisar'
    invented = decide('a@x.example', 'Oi', 'Texto sem data.', False,
                      ai(prazo_texto='dia 30', prazo_iso=date(2026, 11, 30), trecho_prazo='entregar dia 30'), context())
    assert invented['importancia'] == 'revisar' and invented['prazo_iso'] is None and invented['trecho_prazo'] is None
    vague = decide('a@x.example', 'Oi', 'Entrego na semana que vem, a confirmar.', False, ai(importancia='acao'), context())
    assert vague['importancia'] == 'revisar' and vague['prazo_texto'].lower() == 'semana que vem'
    promo = decide('a@x.example', 'Oferta', 'Compre já.', True, ai(categoria='publicidade', importancia='importante'), context())
    assert promo['importancia'] == 'info'
    budget = decide('a@x.example', 'Cotação', 'Segue pedido.', False, ai(importancia='info', categoria='outro'), context())
    assert budget['importancia'] == 'acao'
    date_only = decide('a@x.example', 'Oi', 'Sem qualquer prazo.', False,
                       ai(prazo_iso=date(2026, 11, 30)), context())
    assert date_only['prazo_iso'] is None and date_only['importancia'] == 'revisar'
