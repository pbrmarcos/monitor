import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor import assistant, assistant_drafts as drafts
from monitor.main import create_app
from monitor.models import ChatDraft, ChatMetrics

SOURCE = {'transcription': 'Proposta 77123: peça de 600 mm. Item 88234 recebido. Confirmar especificações da nova peça ou decidir se devolve a recebida.',
          'sender': 'Ana', 'recipient': 'Rafael', 'company': 'Empresa Exemplo', 'situation': 'Uma peça foi recebida; a outra aguarda confirmação.',
          'details': 'Orçamento 77123: peça de 600 mm; item 88234 já recebido.',
          'specifications': 'Peça reta de 600 mm.',
          'pending': ['Confirmar as especificações da proposta 77123', 'Ficar com o item 88234 ou devolver'], 'not_confirmed': ['Prazo de fabricação e envio não informado']}
TEXTS = ['Bom dia, Rafael. Aqui é a Ana, da Empresa Exemplo. Retomo a proposta 77123.',
         'Pode confirmar a especificação de 600 mm na proposta 77123 para darmos andamento?',
         'Sobre o item 88234 já recebido: prefere ficar com ele ou fazer a devolução?',
         'Se facilitar, posso ligar para esclarecer a escolha. Obrigada pelo retorno.']
ALTERNATIVES = ['Bom dia! Para retomarmos a proposta 77123, pode confirmar as especificações e dizer se prefere manter o item 88234 ou devolvê-lo?',
                'Preciso de duas confirmações: especificações da proposta 77123 e escolha entre manter ou devolver o item 88234.',
                'A confirmação da proposta 77123 e a decisão sobre o item 88234 permitem dar andamento ao pedido. Consegue me retornar?',
                'Para facilitar: proposta 77123, responda OK ou Ajustar. Item 88234: Fica ou Devolve. Assim alinhamos os próximos passos.']
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='


@pytest.mark.parametrize('text,kind', [
    ('esse cliente nao me respondeu escreva 4 mensagems proximas que devo enviar na segunda feira', 'sequence'),
    ('Escreva quatro mensagens em sequência', 'sequence'),
    ('quero que escreva 4 mensagens diferentes com abordagens diferentes', 'alternatives'),
    ('agora uma mensagem para 4 tons diferentes', 'alternatives'),
])
def test_last_request_controls_quantity_and_kind_even_with_typo(text, kind):
    request = drafts.plan(text)
    assert request.count == 4 and request.kind == kind and len(request.labels) == 4


def test_counts_are_not_taken_from_business_numbers_or_ordinary_observations():
    assert drafts.plan('Tenho 4 mensagens não lidas e 12 demandas') is None
    assert drafts.plan('Crie 4 demandas para a frente 2') is None
    assert drafts.plan('Escreva 4 mensagens sobre o pedido 12345').count == 4
    assert drafts.plan('Escreva 4 tons: formal, informal, técnico e persuasivo').labels == ('Formal', 'Informal', 'Técnico', 'Persuasivo')


def make(path):
    return TestClient(create_app(path, 'session', False), headers={'Authorization': 'Bearer session'})


def fake(monkeypatch, texts, *, first_invalid=False):
    seen, index = [], 0
    def stream(model, data, messages, window, **kwargs):
        nonlocal index
        seen.append({'model': model, 'messages': messages, 'window': window, **kwargs})
        if kwargs.get('response_format') == drafts.SOURCE_SCHEMA:
            value = SOURCE
        elif first_invalid and index == 0:
            index += 1
            value = {'messages': [{'text': 'Apenas uma resposta incorreta.'}]}
        else:
            offset = index - int(first_invalid)
            value = {'text': texts[offset % len(texts)]}
            index += 1
        yield json.dumps({'delta': json.dumps(value, ensure_ascii=False)})
        yield json.dumps({'done': True, 'metrics': {'input_tokens': 100, 'output_tokens': 20, 'generation_seconds': .5, 'prompt_seconds': .1, 'load_seconds': .01, 'first_token_seconds': .15}})
    monkeypatch.setattr(assistant, 'stream', stream)
    return seen


def ask(api, identifier, question, **kwargs):
    response = api.post(f'/assistant/conversations/{identifier}/messages', json={'content': question, **kwargs})
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines()]


def test_sequence_retries_bad_shape_and_persists_four_messages(tmp_path, monkeypatch):
    seen = fake(monkeypatch, TEXTS, first_invalid=True)
    with make(tmp_path) as api:
        conversation = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        events = ask(api, conversation, 'Escreva 4 mensagens próximas para enviar ao cliente. Orçamento 77123: peça de 600 mm. Item 88234 já recebido.', task='next_messages')
        bundle = next(event['drafts'] for event in events if event.get('drafts'))
        assert bundle['kind'] == 'sequence' and len(bundle['items']) == 4
        assert [item['text'] for item in bundle['items']] == TEXTS
        assert events[-1]['metrics']['model_calls'] == 5 and events[-1]['metrics']['attempts'] == 2
        assert events[-1]['metrics']['output_tokens'] == 100
        assert all(call['window'] == 16384 for call in seen)
        assert 'Opção 1:' not in seen[-1]['extra_system']
        assert not any('Apenas uma resposta incorreta' in event.get('delta', '') for event in events)
        assert api.get(f'/assistant/conversations/{conversation}/messages').json()[-1]['drafts'] == bundle
    with make(tmp_path) as api:
        assert len(api.get(f'/assistant/conversations/{conversation}/messages').json()[-1]['drafts']['items']) == 4
        api.delete('/assistant/records')
        assert api.get(f'/assistant/conversations/{conversation}/messages').json()[-1]['drafts'] == bundle
        api.delete(f'/assistant/conversations/{conversation}')
        with Session(api.app.state.engine) as db:
            assert db.exec(select(ChatDraft)).all() == [] and db.exec(select(ChatMetrics)).all() == []


def test_repeated_messages_never_become_four_labelled_copies(tmp_path, monkeypatch):
    seen = fake(monkeypatch, ['Esta é exatamente a mesma mensagem repetida ao cliente.'])
    with make(tmp_path) as api:
        identifier = api.post('/assistant/conversations', json={'mode': 'general'}).json()['id']
        events = ask(api, identifier, 'Escreva 4 mensagens diferentes')
        assert events[-1].get('error') and not any(event.get('drafts') for event in events)
        assert len(seen) == 3  # primeiro item + duas tentativas do item repetido


def test_followup_reuses_image_facts_and_changes_to_four_tones(tmp_path, monkeypatch):
    seen = fake(monkeypatch, TEXTS)
    with make(tmp_path) as api:
        identifier = api.post('/assistant/conversations', json={'mode': 'work'}).json()['id']
        image = api.post('/assistant/attachments', json={'name': 'exemplo.png', 'data': PNG}).json()
        first = ask(api, identifier, 'Escreva 4 mensagens próximas', attachments=[image['id']])
        assert next(event['drafts'] for event in first if event.get('drafts'))['kind'] == 'sequence'
        assert len(seen) == 1 and seen[0]['messages'][-1]['images'] == [PNG]
        seen = fake(monkeypatch, ALTERNATIVES)
        second = ask(api, identifier, 'agora uma mensagem para 4 tons diferentes')
        bundle = next(event['drafts'] for event in second if event.get('drafts'))
        assert bundle['kind'] == 'alternatives' and len(bundle['items']) == 4
        assert len(seen) == 0  # o contexto e as pendências lidas foram reutilizados no playbook
        assert bundle['method'] == 'guided'
        assert all('77123' in item['text'] and '88234' in item['text'] for item in bundle['items'])
        assert second[-1]['metrics']['model_calls'] == 0


def test_new_numbers_and_unsupported_deadlines_are_rejected():
    with pytest.raises(ValueError):
        drafts.check_facts('Confirme até sexta-feira e enviaremos amanhã.', 'Pode responder na segunda-feira.', [])
    with pytest.raises(ValueError):
        drafts.check_facts('O preço é R$ 9.999,00.', 'O preço é R$ 1.250,00.', [])
    with pytest.raises(ValueError):
        drafts.check_facts('Aguardo a escolha da peça.', 'Item 88234.', ['88234'])
    drafts.check_facts('Filamento de 0,7 mm e proposta 77123.', 'Filamento 0,70 mm; proposta 77123.', ['77123'])


def test_guided_workflow_keeps_people_and_decisions_separate_without_fake_urgency():
    bundle = drafts.guided_commercial(drafts.plan('Escreva 4 mensagens próximas'), SOURCE)
    assert len(bundle['items']) == 4
    assert bundle['items'][0]['text'].startswith('Olá, Rafael!') and 'Ana' in bundle['items'][0]['text']
    assert 'especificações' in bundle['items'][1]['text'] and '77123' in bundle['items'][1]['text'] and '600 mm' in bundle['items'][1]['text']
    assert '88234' in bundle['items'][2]['text'] and 'devolução' in bundle['items'][2]['text']
    assert all('sexta' not in item['text'] and 'hoje' not in item['text'] for item in bundle['items'])
    assert drafts.guided_commercial(drafts.plan('Escreva 4 tons'), SOURCE, 'Ele já confirmou as medidas e devolveu a peça') is None
