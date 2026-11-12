"""Opt-in Windows vault check using only an isolated synthetic credential."""
from uuid import uuid4
from monitor.secrets_store import KeyringStore

if __name__ == '__main__':
    vault = KeyringStore()
    reference, value = f'qa:{uuid4()}', uuid4().hex
    try:
        vault.set(reference, value)
        assert vault.get(reference) == value
    finally:
        vault.delete(reference)
    assert vault.get(reference) is None
    print('Windows Credential Manager: synthetic write, read and cleanup OK')
