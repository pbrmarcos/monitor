import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from monitor import social
from monitor.main import create_app
from monitor.models import SocialSnapshot

HEADERS = {'Authorization': 'Bearer session'}
TOKEN = 'IGAAtoken_de_teste_1234567890'
PNG = 'data:image/png;base64,iVBORw0KGgo='


def test_preferences_rename_fronts_and_validate_colors(tmp_path):
    with TestClient(create_app(tmp_path, 'session', False), headers=HEADERS) as api:
        initial = api.get('/preferences').json()
        assert initial['fronts'] == ['Rocha Comercial', 'Nextlink', 'Carteira Pronta', 'WebQ']
        assert initial['primary'] == '#0D213A' and initial['name'] == 'Marcos'
        wanted = {**initial, 'name': ' Marcos Rocha ', 'tagline': 'Diretor', 'avatar': PNG,
                  'fronts': ['Rocha', 'Next ', 'Carteira', 'WebQ'], 'primary': '#14342b', 'accent': '#F2B705'}
        saved = api.put('/preferences', json=wanted).json()
        assert saved['name'] == 'Marcos Rocha' and saved['fronts'][1] == 'Next' and saved['primary'] == '#14342B'
        assert api.get('/preferences').json() == saved
        for bad in ({'primary': '#FFE066'}, {'primary': 'azul'}, {'fronts': ['A', 'B', 'C']}, {'fronts': ['A', 'B', 'C', '']},
                    {'avatar': 'data:text/html;base64,PHNjcmlwdD4='}, {'name': ''}):
            assert api.put('/preferences', json={**wanted, **bad}).status_code == 422
        assert api.get('/preferences').json() == saved


def test_renamed_front_reaches_the_assistant_context(tmp_path, monkeypatch):
    real_client, seen = httpx.Client, []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=json.dumps({'message': {'content': 'ok'}}))

    monkeypatch.setattr('monitor.assistant.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    with TestClient(create_app(tmp_path, 'session', False), headers=HEADERS) as api:
        current = api.get('/preferences').json()
        api.put('/preferences', json={**current, 'fronts': ['Rocha', 'Loja Nova', 'Carteira', 'WebQ']})
        api.post('/demands', json={'title': 'Proposta', 'front_id': 2})
        api.post('/assistant/chat', json={'messages': [{'role': 'user', 'content': 'Oi'}]})
        assert '[D1] Proposta | Loja Nova' in seen[-1]['messages'][0]['content']


class FakeInstagram:
    def __init__(self):
        self.followers, self.requests, self.broken, self.stories = 1200, [], False, True
        self.now = datetime.now(timezone.utc)

    def stamp(self, days):
        return (self.now - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S+0000')

    def __call__(self, request):
        self.requests.append(request)
        if request.url.host == 'cdn.example':
            return httpx.Response(200, content=b'\x89PNG', headers={'content-type': 'image/png'})
        assert request.url.host == 'graph.instagram.com'
        if self.broken or request.url.params['access_token'] != TOKEN:
            return httpx.Response(400, json={'error': {'code': 190, 'message': 'expired'}})
        path = request.url.path
        if path == '/me':
            return httpx.Response(200, json={'user_id': '178', 'username': 'rochacomercial', 'name': 'Rocha Comercial',
                                             'profile_picture_url': 'https://cdn.example/a.png',
                                             'followers_count': self.followers, 'media_count': 87})
        if path == '/me/media':
            return httpx.Response(200, json={'data': [
                {'id': 'p1', 'media_product_type': 'FEED', 'timestamp': self.stamp(1), 'like_count': 40, 'comments_count': 3},
                {'id': 'p2', 'media_product_type': 'REELS', 'timestamp': self.stamp(5), 'like_count': 110, 'comments_count': 9},
                {'id': 'p3', 'media_product_type': 'FEED', 'timestamp': self.stamp(20), 'like_count': 500, 'comments_count': 50}]})
        if path == '/me/stories':
            if not self.stories:
                return httpx.Response(400, json={'error': {'code': 10}})
            return httpx.Response(200, json={'data': [{'id': 's1', 'timestamp': self.stamp(0)}]})
        raise AssertionError(path)


@pytest.fixture
def instagram(monkeypatch):
    fake = FakeInstagram()
    monkeypatch.setattr(social, 'TRANSPORT', httpx.MockTransport(fake))
    return fake


def test_instagram_profile_collects_weekly_numbers(tmp_path, instagram):
    with TestClient(create_app(tmp_path, 'session', False), headers=HEADERS) as api:
        assert api.post('/social', json={'front_id': 1, 'token': 'IGAAtoken_errado_1234567890'}).status_code == 400
        assert api.get('/social').json() == []
        profile = api.post('/social', json={'front_id': 1, 'token': TOKEN}).json()
        assert TOKEN not in json.dumps(profile) and api.app.state.vault.get('instagram:178') == TOKEN
        assert profile['username'] == 'rochacomercial' and profile['avatar'].startswith('data:image/png;base64,')
        assert (profile['followers'], profile['posts'], profile['status']) == (1200, 87, 'ok')
        assert (profile['posts_week'], profile['likes_week'], profile['comments_week'], profile['stories_week']) == (2, 150, 12, 1)
        assert profile['followers_change'] is None  # primeira coleta: ainda sem comparação
        assert api.post('/social', json={'front_id': 2, 'token': TOKEN}).status_code == 409

        with Session(api.app.state.engine) as db:  # coleta de 9 dias atrás
            db.add(SocialSnapshot(profile_id=profile['id'], day=date.today() - timedelta(days=9), followers=1150, media_count=84))
            db.commit()
        instagram.followers, instagram.stories = 1234, False
        again = api.post(f'/social/{profile["id"]}/sync').json()
        assert (again['followers'], again['followers_change'], again['change_days']) == (1234, 84, 7)
        assert again['stories_week'] is None and again['posts_week'] == 2  # sem acesso a stories: não inventa zero
        assert len(api.get('/social').json()) == 1

        instagram.broken = True
        failed = api.post(f'/social/{profile["id"]}/sync').json()
        assert failed['status'] == 'erro' and 'token expirou' in failed['status_detail'] and failed['followers'] == 1234
        assert TOKEN not in json.dumps(failed)

        assert api.delete(f'/social/{profile["id"]}').status_code == 204
        assert api.get('/social').json() == [] and api.app.state.vault.get('instagram:178') is None


def test_demo_mode_does_not_connect_profiles(tmp_path, instagram):
    with TestClient(create_app(tmp_path, 'session', True), headers=HEADERS) as api:
        assert api.post('/social', json={'front_id': 1, 'token': TOKEN}).status_code == 409
    assert instagram.requests == []
