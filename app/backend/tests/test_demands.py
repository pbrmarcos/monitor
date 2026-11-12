from fastapi.testclient import TestClient
from monitor.main import create_app


def client(tmp_path):
    return TestClient(create_app(tmp_path, token='test-session', demo=False), headers={'Authorization': 'Bearer test-session'})


def test_authentication_and_validation(tmp_path):
    with client(tmp_path) as api:
        assert api.get('/demands', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        assert api.post('/demands', json={'title': '  ', 'front_id': 1}).status_code == 422
        assert api.post('/demands', json={'title': 'Proposta', 'front_id': 5}).status_code == 422


def test_persistence_history_and_followup(tmp_path):
    with client(tmp_path) as api:
        created = api.post('/demands', json={'title': 'Proposta', 'front_id': 1})
        assert created.status_code == 201
        demand = created.json()
        demand['stage'] = 'acompanhar'
        assert api.put(f"/demands/{demand['id']}", json=demand).status_code == 422
        demand['return_date'] = '2026-12-15'
        assert api.put(f"/demands/{demand['id']}", json=demand).status_code == 200
        assert len(api.get(f"/demands/{demand['id']}/events").json()) == 2
        assert api.get(f"/demands/{demand['id']}/events").json()[0]['created_at'].endswith(('+00:00', 'Z'))
    with client(tmp_path) as api:
        assert api.get('/demands').json()[0]['return_date'] == '2026-12-15'
        assert api.delete(f"/demands/{demand['id']}").status_code == 204
        assert api.get('/demands').json() == []


def test_demo_is_separate_and_seeded_once(tmp_path):
    for _ in range(2):
        with TestClient(create_app(tmp_path, 'token', True), headers={'Authorization': 'Bearer token'}) as api:
            assert len(api.get('/demands').json()) == 4
    with client(tmp_path) as api:
        assert api.get('/demands').json() == []
