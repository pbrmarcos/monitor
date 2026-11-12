from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from monitor.main import create_app
from monitor import reminders
from monitor.models import Reminder, Notice, Email, EmailAccount, EmailAnalysis

HEADERS = {'Authorization': 'Bearer session'}
THURSDAY = datetime(2026, 11, 12, 10, 30, tzinfo=timezone.utc)  # 07:30 Sao Paulo


def make(tmp_path):
    app = create_app(tmp_path, 'session', False)
    return app, TestClient(app, headers=HEADERS)


def test_reminder_restart_delivery_ack_and_privacy(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        item = api.post('/reminders', json={'text':'Retornar proposta confidencial', 'when':'2026-11-12T07:00:00-03:00'}).json()
        assert api.get('/reminders').json()[0]['when'].endswith(('+00:00','Z'))
        reminders.generate(app.state.engine, THURSDAY)
        reminders.generate(app.state.engine, THURSDAY)
        feed = api.get('/notifications/desktop').json()
        assert len(feed) == 2  # reminder and digest once only
        assert all('confidencial' not in n['body'] for n in feed)
        for notice in feed:
            assert api.post(f"/notifications/{notice['id']}/delivered").status_code == 204
        assert api.get('/notifications/desktop').json() == []
    app, client = make(tmp_path)
    with client as api:
        reminders.generate(app.state.engine, THURSDAY)
        assert len(api.get('/notifications').json()) == 2
        assert api.get('/reminders').json()[0]['status'] == 'disparado'
        assert api.post(f"/reminders/{item['id']}/complete").json()['status'] == 'concluido'
        assert all(n['read'] for n in api.get('/notifications').json() if n['kind'] == 'lembrete')


def test_reschedule_cancel_and_demand_deletion(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        demand = api.post('/demands', json={'title':'Proposta','front_id':1}).json()
        payload = {'text':'Retorno','when':THURSDAY.isoformat(),'demand_id':demand['id']}
        identifier = api.post('/reminders', json=payload).json()['id']
        reminders.generate(app.state.engine, THURSDAY)
        later = THURSDAY + timedelta(minutes=15)
        assert api.put(f'/reminders/{identifier}', json={**payload,'when':later.isoformat()}).status_code == 200
        reminders.generate(app.state.engine, THURSDAY)
        assert api.get('/reminders').json()[0]['status'] == 'pendente'
        assert len([n for n in api.get('/notifications/desktop').json() if n['demand_id']]) == 0
        reminders.generate(app.state.engine, later)
        assert len([n for n in api.get('/notifications').json() if n['kind']=='lembrete']) == 2
        assert api.delete(f"/demands/{demand['id']}").status_code == 204
        assert api.get('/reminders').json()[0]['status'] == 'cancelado'
        assert api.get('/reminders').json()[0]['demand_id'] is None
        assert not any(n['demand_id'] for n in api.get('/notifications/desktop').json())


def test_daily_digest_weekdays_timezone_and_late_start(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        reminders.generate(app.state.engine, THURSDAY - timedelta(minutes=1))
        assert api.get('/notifications').json() == []
        reminders.generate(app.state.engine, THURSDAY + timedelta(hours=4))
        reminders.generate(app.state.engine, THURSDAY + timedelta(hours=5))
        assert len(api.get('/notifications').json()) == 1
        reminders.generate(app.state.engine, THURSDAY + timedelta(days=2))
        assert len(api.get('/notifications').json()) == 1  # Saturday
        settings=api.get('/agenda/settings').json()
        api.put('/agenda/settings', json={**settings,'timezone':'UTC','summary_time':'10:31'})
        friday=THURSDAY+timedelta(days=1)
        reminders.generate(app.state.engine, friday)
        assert len(api.get('/notifications').json()) == 1
        reminders.generate(app.state.engine, friday+timedelta(minutes=1))
        assert len(api.get('/notifications').json()) == 2
        assert api.put('/agenda/settings', json={**settings,'timezone':'Invalid/Zone'}).status_code == 422


def test_validation_completed_demands_and_notifications_disabled(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        assert api.post('/reminders', json={'text':'X','when':'2026-11-12T07:00:00'}).status_code == 422
        assert api.post('/reminders', json={'text':' ','when':THURSDAY.isoformat()}).status_code == 422
        assert api.post('/reminders', json={'text':'X','when':THURSDAY.isoformat(),'demand_id':999}).status_code == 404
        settings=api.get('/agenda/settings').json()
        api.put('/agenda/settings', json={**settings,'notifications_enabled':False})
        identifier=api.post('/reminders', json={'text':'Somente no app','when':THURSDAY.isoformat()}).json()['id']
        reminders.generate(app.state.engine, THURSDAY)
        assert api.get('/notifications/desktop').json() == []
        assert len(api.get('/notifications').json()) == 2
        api.post(f'/reminders/{identifier}/cancel')
        assert api.get('/reminders').json()[0]['status']=='cancelado'
        demand=api.post('/demands',json={'title':'Concluída','front_id':1,'stage':'ganho'}).json()
        api.post('/reminders',json={'text':'Não avisar','when':THURSDAY.isoformat(),'demand_id':demand['id']})
        reminders.generate(app.state.engine, THURSDAY)
        assert len(api.get('/notifications').json()) == 2


def test_auto_email_reminders_opt_in_evidence_and_cancel_persistence(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        with Session(app.state.engine) as db:
            account=EmailAccount(front_id=1,address='a@example.com',host='imap.example.com',username='a',keyring_ref='fake')
            db.add(account);db.flush()
            mail=Email(account_id=account.id,message_id='auto@test',subject='Contrato',body_text='Envie até 13/11.')
            db.add(mail);db.flush()
            db.add(EmailAnalysis(email_id=mail.id,provisional=False,importancia='acao',confianca=.95,
                                 prazo_iso=THURSDAY.date()+timedelta(days=1),trecho_prazo='Envie até 13/11.'))
            invented=Email(account_id=account.id,message_id='invented@test',subject='Olá',body_text='Apenas uma informação.')
            db.add(invented);db.flush()
            db.add(EmailAnalysis(email_id=invented.id,provisional=False,importancia='acao',confianca=.99,
                                 prazo_iso=THURSDAY.date()+timedelta(days=1),trecho_prazo='Apenas uma informação.'))
            db.commit()
        reminders.generate(app.state.engine, THURSDAY)
        assert api.get('/reminders').json() == []
        settings=api.get('/agenda/settings').json()
        api.put('/agenda/settings',json={**settings,'auto_email_reminders':True})
        reminders.generate(app.state.engine, THURSDAY)
        items=api.get('/reminders').json()
        assert len(items)==1 and 'T12:00:00' in items[0]['when']  # 9am local -> UTC
        linked=api.post('/demands',json={'title':'Contrato','front_id':1,'origin_ref':'email:1'}).json()
        assert api.get('/reminders').json()[0]['demand_id']==linked['id']
        api.post(f"/reminders/{items[0]['id']}/cancel")
        reminders.generate(app.state.engine, THURSDAY)
        assert len(api.get('/reminders').json()) == 1
        assert api.get('/reminders').json()[0]['status']=='cancelado'


def test_closing_demand_finishes_existing_reminder_and_same_time_edit_is_new_revision(tmp_path):
    app, client = make(tmp_path)
    with client as api:
        demand=api.post('/demands',json={'title':'Retorno','front_id':1}).json()
        payload={'text':'Retornar','when':THURSDAY.isoformat(),'demand_id':demand['id']}
        item=api.post('/reminders',json=payload).json()
        reminders.generate(app.state.engine, THURSDAY)
        api.put(f"/reminders/{item['id']}",json={**payload,'text':'Retornar novamente'})
        reminders.generate(app.state.engine, THURSDAY)
        assert len([n for n in api.get('/notifications').json() if n['kind']=='lembrete']) == 2
        assert api.get('/agenda/alert').json()['active']
        assert api.put(f"/demands/{demand['id']}",json={**demand,'stage':'ganho'}).status_code == 200
        assert api.get('/reminders').json()[0]['status']=='concluido'
        assert not [n for n in api.get('/notifications/desktop').json() if n['demand_id']]
