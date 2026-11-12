"""Pasta de arquivos escolhida pelo usuário (normalmente no OneDrive), backups e exportações.

O banco ativo continua em %LOCALAPPDATA%: SQLite dentro de uma pasta sincronizada pode
corromper. O que vai para a nuvem são cópias consistentes e os arquivos gerados.
"""
import csv
import os
import sqlite3
from datetime import date
from pathlib import Path

FOLDERS = ('Backups', 'Entrada', 'Exportações')
KEEP_BACKUPS = 14
README = (
    'Esta pasta pertence ao Monitor.\r\n\r\n'
    'Backups      cópias diárias do banco de dados (as 14 mais recentes)\r\n'
    'Entrada      arquivos que você quer que o Monitor organize\r\n'
    'Exportações  planilhas geradas pelo Monitor\r\n\r\n'
    'Senhas e tokens nunca são gravados aqui.\r\n'
)


class StorageError(Exception):
    pass


def installer_choice() -> str | None:
    """Pasta escolhida no instalador, gravada em HKCU\\Software\\Monitor."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Monitor') as key:
            return str(winreg.QueryValueEx(key, 'FilesDir')[0]).strip() or None
    except (ImportError, OSError):
        return None


def onedrive_roots() -> list[Path]:
    roots = []
    for name in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        value = os.environ.get(name)
        if value and Path(value) not in roots:
            roots.append(Path(value))
    return roots


def in_onedrive(folder: Path) -> bool:
    return any(folder == root or root in folder.parents for root in onedrive_roots())


def suggestion() -> str:
    roots = onedrive_roots()
    return str((roots[0] if roots else Path.home() / 'Documents') / 'Monitor')


def prepare(value: str) -> Path:
    """Valida a pasta escolhida e cria a estrutura do Monitor dentro dela."""
    folder = Path(value.strip().strip('"'))
    if not value.strip() or not folder.is_absolute():
        raise StorageError('Informe o caminho completo da pasta, por exemplo C:\\Users\\voce\\OneDrive\\Monitor.')
    try:
        for name in FOLDERS:
            (folder / name).mkdir(parents=True, exist_ok=True)
        note = folder / 'LEIA-ME.txt'
        if not note.exists():
            note.write_text(README, encoding='utf-8-sig')
    except OSError:
        raise StorageError('Não foi possível criar ou gravar nessa pasta. Escolha outra ou confira as permissões.') from None
    return folder


def last_backup(folder: Path) -> str | None:
    files = sorted((folder / 'Backups').glob('monitor-*.db')) if (folder / 'Backups').is_dir() else []
    return files[-1].stem.removeprefix('monitor-') if files else None


def backup(database: Path, folder: Path) -> Path:
    """Cópia consistente do banco pela API de backup do SQLite; mantém as mais recentes."""
    target = folder / 'Backups' / f'monitor-{date.today().isoformat()}.db'
    partial = target.with_suffix('.parcial')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(database)
        copy = sqlite3.connect(partial)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
        os.replace(partial, target)
        for old in sorted(target.parent.glob('monitor-*.db'))[:-KEEP_BACKUPS]:
            old.unlink()
    except (OSError, sqlite3.Error):
        partial.unlink(missing_ok=True)
        raise StorageError('Não foi possível gravar o backup na pasta de arquivos.') from None
    return target


def export_demands(rows: list[dict], folder: Path) -> Path:
    target = folder / 'Exportações' / f'demandas-{date.today().isoformat()}.csv'
    columns = ['id', 'title', 'front_id', 'contact', 'channel', 'stage', 'priority', 'due', 'return_date', 'next_action', 'summary']
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        raise StorageError('Não foi possível gravar a planilha na pasta de arquivos.') from None
    return target
