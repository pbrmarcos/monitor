import copy
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor import social, social_browser
from monitor.main import create_app
from monitor.models import Demand, SocialProfile, now
from monitor.secrets_store import MemoryStore

HEADERS = {'Authorization': 'Bearer session'}


@pytest.fixture
def browser_account(tmp_path, monkeypatch):
    directory = tmp_path / 'perfis' / 'conta-1'
    (directory / 'Default').mkdir(parents=True)
    account = {'account_id': 1, 'username': 'empresa', 'name': 'Empresa', 'path': str(directory)}
    monkeypatch.setattr(social_browser, 'discover', lambda: [account])
    return account


def sample():
    instant = now()
    return {'account_id': '123', 'name': 'Empresa', 'followers': 350, 'posts': 20, 'detail': '',
            'media': [{'id': '50', 'published_at': instant, 'likes': 8, 'comments': 4}],
            'comments': [{'id': '901', 'author': 'cliente', 'text': 'Qual o valor do serviço?', 'post_url': 'https://www.instagram.com/p/ABC/', 'published_at': instant},
                         {'id': '902', 'author': 'amigo', 'text': 'Adorei o trabalho!', 'post_url': 'https://www.instagram.com/p/ABC/', 'published_at': instant},
                         {'id': '903', 'author': 'empresa', 'text': 'Quer um orçamento?', 'post_url': 'https://www.instagram.com/p/ABC/', 'published_at': instant},
                         {'id': '904', 'author': 'antigo', 'text': 'Preciso de um orçamento', 'post_url': 'https://www.instagram.com/p/ABC/', 'published_at': instant - timedelta(days=20)}]}


def connect(api, automatic=True):
    response = api.post('/social/browser', json={'account_id': 1, 'front_id': 2, 'auto_demands': automatic})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_browser_collection_creates_only_new_clear_demands_and_deduplicates(tmp_path, monkeypatch, browser_account):
    payload = sample()
    monkeypatch.setattr(social_browser, 'collect', lambda *args: copy.deepcopy(payload))
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        assert api.get('/social/browser/profiles').json()[0]['username'] == 'empresa'
        identifier = connect(api)
        assert api.post('/social/browser', json={'account_id': 1, 'front_id': 1}).status_code == 409
        assert api.post('/social/browser', json={'account_id': 999, 'front_id': 1}).status_code == 404
        route = f'/social/{identifier}'
        for _ in range(2):
            result = api.post(route + '/sync').json()
            assert result['followers'] == 350 and result['method'] == 'browser' and result['stories_week'] is None
        records, demands = api.get('/social/comments').json(), api.get('/demands').json()
        assert len(records) == 3 and len(demands) == 1
        assert demands[0]['channel'] == 'instagram' and demands[0]['front_id'] == 2
        assert demands[0]['origin_ref'] == 'instagram:901'
        assert next(c for c in records if c['comment_id'] == '904')['status'] == 'revisar'
        assert next(c for c in records if c['comment_id'] == '902')['status'] == 'informativo'
        # A origem do Instagram continua válida quando o usuário edita a demanda.
        edited = {key: demands[0][key] for key in ('title', 'front_id', 'channel', 'origin_ref')}
        assert api.put(f"/demands/{demands[0]['id']}", json=edited).status_code == 200
        assert api.delete(route).status_code == 204
        identifier = connect(api)
        api.post(f'/social/{identifier}/sync')
        assert len(api.get('/demands').json()) == 1  # reconectar não duplica pedidos


def test_manual_review_pause_and_last_data_survive_errors(tmp_path, monkeypatch, browser_account):
    monkeypatch.setattr(social_browser, 'collect', lambda *args: sample())
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        identifier = connect(api, False)
        route = f'/social/{identifier}'
        first = api.post(route + '/sync').json()
        assert api.get('/demands').json() == []
        record = api.get('/social/comments').json()[0]
        accepted = api.post(f"/social/comments/{record['id']}/accept").json()
        assert accepted['demand_id']
        assert api.post(f"/social/comments/{record['id']}/accept").json() == accepted
        assert len(api.get('/demands').json()) == 1
        calls = []
        def failure(*args):
            calls.append(1)
            raise social_browser.BrowserError('Faça login no Prospect.', 'login')
        monkeypatch.setattr(social_browser, 'collect', failure)
        failed = api.post(route + '/sync').json()
        assert failed['followers'] == first['followers'] and failed['last_sync'] == first['last_sync']
        assert failed['status'] == 'login'
        social.sync(api.app.state.engine, api.app.state.vault)
        assert len(calls) == 1  # nenhuma repetição automática após desafio
        api.put(route + '/browser', json={'enabled': False, 'auto_demands': True})
        api.post(route + '/sync')
        assert len(calls) == 1
        api.put(route + '/browser', json={'enabled': True, 'auto_demands': True})
        social.sync(api.app.state.engine, api.app.state.vault)
        assert len(calls) == 2


def test_browser_is_blocked_in_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(social_browser, 'discover', lambda: pytest.fail('Demo acessou perfis reais'))
    with TestClient(create_app(tmp_path, 'session', True), headers=HEADERS) as api:
        assert api.get('/social/browser/profiles').status_code == 409
        assert api.post('/social/browser', json={'account_id': 1, 'front_id': 1}).status_code == 409


@pytest.mark.parametrize('message,expected', [('Quero um orçamento', True), ('Quanto custa?', True), ('Como contratar?', True), ('Não recebi meu pedido', True), ('Lindo trabalho!', False), ('Adorei o orçamento', False)])
def test_commercial_request(message, expected):
    assert social.commercial_request(message) is expected


class Page:
    url = 'https://www.instagram.com/empresa/'
    def __init__(self, replies, identity='123'):
        self.replies, self.identity, self.paths = replies, identity, []
    def goto(self, *args, **kwargs):
        pass
    def evaluate(self, expression, path=None):
        if path is None:
            return self.identity
        self.paths.append(path)
        return self.replies.pop(0)


def test_reader_parses_pagination_and_requires_own_identity():
    instant = int(now().timestamp())
    user = {'status': 200, 'body': {'data': {'user': {'id': '123', 'username': 'empresa', 'edge_followed_by': {'count': 350}, 'edge_owner_to_timeline_media': {'count': 20}}}}}
    feed = {'status': 200, 'body': {'items': [{'pk': 50, 'code': 'ABC', 'taken_at': instant, 'like_count': 8, 'comment_count': 2}]}}
    comments = lambda identifier: {'pk': identifier, 'text': 'Qual o valor?', 'user': {'username': 'cliente'}, 'created_at': instant}
    page = Page([user, feed, {'status': 200, 'body': {'comments': [comments(901)], 'has_more_comments': True, 'next_min_id': 'next'}}, {'status': 200, 'body': {'comments': [comments(902)], 'has_more_comments': False}}])
    result = social_browser.read_account(page, 'empresa')
    assert len(result['comments']) == 2 and 'min_id=next' in page.paths[-1]
    with pytest.raises(social_browser.BrowserError, match='sessão'):
        social_browser.read_account(Page([user], identity='999'), 'empresa')


@pytest.mark.parametrize('reply,status', [({'status': 429, 'body': {}}, 'limitado'), ({'status': 200, 'body': {'message': 'challenge_required'}}, 'login'), ({'status': 403, 'body': {}}, 'login')])
def test_reader_stops_on_authentication_or_rate_limit(reply, status):
    import time
    with pytest.raises(social_browser.BrowserError) as error:
        social_browser.request(Page([reply]), '/api/v1/test/', time.monotonic() + 10)
    assert error.value.status == status


def test_profile_lock_does_not_launch_when_prospect_is_using_it(tmp_path, monkeypatch):
    directory = tmp_path / 'conta-1'
    (directory / 'Default').mkdir(parents=True)
    monkeypatch.setattr(social_browser, 'profile_in_use', lambda path: True)
    with pytest.raises(social_browser.BrowserError) as error:
        with social_browser.profile_lock(directory):
            pytest.fail('Perfil ocupado não deveria ser aberto')
    assert error.value.status == 'ocupado'


@pytest.mark.parametrize('text,expected', [('1.234', 1234), ('1,234', 1234), ('123', 123), ('1,2 mil', None), ('1.2', None)])
def test_only_exact_visible_totals_are_accepted(text, expected):
    assert social_browser.exact_number(text) == expected


def test_old_social_schema_preserves_api_account_and_adds_browser_fields(tmp_path):
    import sqlite3
    with sqlite3.connect(tmp_path / 'monitor.db') as db:
        db.execute("CREATE TABLE socialprofile (id INTEGER PRIMARY KEY, front_id INTEGER NOT NULL, network VARCHAR NOT NULL, account_id VARCHAR NOT NULL UNIQUE, username VARCHAR NOT NULL, name VARCHAR NOT NULL, avatar VARCHAR NOT NULL, keyring_ref VARCHAR NOT NULL, token_at DATETIME, stories_ok BOOLEAN NOT NULL, status VARCHAR NOT NULL, status_detail VARCHAR NOT NULL, last_sync DATETIME)")
        db.execute("INSERT INTO socialprofile VALUES(1, 2, 'instagram', '123', 'empresa', '', '', 'instagram:123', NULL, 1, 'ok', '', NULL)")
    with TestClient(create_app(tmp_path, 'session', False, secret_store=MemoryStore()), headers=HEADERS) as api:
        profile = api.get('/social').json()[0]
        assert profile['username'] == 'empresa' and profile['method'] == 'api' and profile['enabled']
        with Session(api.app.state.engine) as db:
            assert db.get(SocialProfile, 1).keyring_ref == 'instagram:123'
