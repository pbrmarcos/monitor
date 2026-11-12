import sqlite3
import csv

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from monitor.main import create_app, migrate
from monitor.storage import export_demands

HEADERS = {'Authorization': 'Bearer session'}


def test_export_keeps_untrusted_values_as_text(tmp_path):
    path = export_demands([{'title': '=1+1', 'contact': ' @SUM(1)', 'summary': 'Texto normal'}], tmp_path)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        row = next(csv.DictReader(handle, delimiter=';'))
    assert row['title'] == "'=1+1" and row['contact'] == "' @SUM(1)"
    assert row['summary'] == 'Texto normal'


def test_files_folder_backup_and_export(tmp_path):
    data, cloud = tmp_path / 'dados', tmp_path / 'OneDrive' / 'Monitor'
    with TestClient(create_app(data, 'session', False), headers=HEADERS) as api:
        assert api.get('/storage').json()['files_dir'] is None
        assert api.post('/storage/backup').status_code == 409
        assert api.put('/storage', json={'files_dir': 'pasta-relativa'}).status_code == 400
        status = api.put('/storage', json={'files_dir': str(cloud)}).json()
        assert status['ready'] and status['source'] == 'configuracao'
        assert {p.name for p in cloud.iterdir()} == {'Backups', 'Entrada', 'Exportações', 'LEIA-ME.txt'}
        api.post('/demands', json={'title': 'Proposta; com "aspas"', 'front_id': 1})
        backup = api.post('/storage/backup').json()['file']
        copy = sqlite3.connect(backup)
        assert copy.execute('SELECT title FROM demand').fetchone()[0].startswith('Proposta')
        copy.close()
        assert api.get('/storage').json()['last_backup'] is not None
        export = api.post('/storage/export-demands').json()['file']
        with open(export, encoding='utf-8-sig') as handle:
            assert 'Proposta; com ""aspas""' in handle.read()
    assert not (cloud / 'monitor.db').exists() and (data / 'monitor.db').exists()  # banco ativo fora da nuvem


def test_installer_choice_is_the_default_until_changed(tmp_path):
    chosen = tmp_path / 'instalador'
    app = create_app(tmp_path / 'dados', 'session', False, default_files_dir=str(chosen))
    with TestClient(app, headers=HEADERS) as api:
        status = api.get('/storage').json()
        assert status['files_dir'] == str(chosen) and status['source'] == 'instalador' and not status['ready']
        assert api.post('/storage/backup').status_code == 200 and (chosen / 'Backups').is_dir()


def test_migration_upgrades_a_phase_one_database(tmp_path):
    path = tmp_path / 'monitor.db'
    old = sqlite3.connect(path)
    old.executescript('''
        CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
        INSERT INTO schema_migrations VALUES (1);
        CREATE TABLE demand (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, front_id INTEGER NOT NULL,
            contact VARCHAR NOT NULL, channel VARCHAR NOT NULL, stage VARCHAR NOT NULL, priority VARCHAR NOT NULL,
            due DATE, next_action VARCHAR NOT NULL, return_date DATE, summary VARCHAR NOT NULL, created_at DATETIME NOT NULL);
        INSERT INTO demand VALUES (1, 'Antiga', 1, '', 'manual', 'novo', 'normal', NULL, '', NULL, '', '2026-11-01 10:00:00');
    ''')
    old.commit()
    old.close()
    with TestClient(create_app(tmp_path, 'session', False), headers=HEADERS) as api:
        demand = api.get('/demands').json()[0]
        assert demand['title'] == 'Antiga' and demand['origin_ref'] == '' and demand['created_by'] == 'usuario'
    engine = create_engine(f'sqlite:///{path}')
    migrate(engine)  # idempotente
    engine.dispose()
