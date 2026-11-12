"""Senhas ficam no Gerenciador de Credenciais do Windows, nunca no banco nem em logs."""
SERVICE = 'Monitor'


class SecretError(Exception):
    pass


class KeyringStore:
    def _keyring(self):
        try:
            import keyring
            from keyring.backends.Windows import WinVaultKeyring
            keyring.set_keyring(WinVaultKeyring())
            return keyring
        except Exception:
            raise SecretError('O Gerenciador de Credenciais do Windows não está disponível.') from None

    def set(self, ref: str, secret: str) -> None:
        try:
            self._keyring().set_password(SERVICE, ref, secret)
        except SecretError:
            raise
        except Exception:
            raise SecretError('Não foi possível guardar a senha no Gerenciador de Credenciais.') from None

    def get(self, ref: str) -> str | None:
        try:
            return self._keyring().get_password(SERVICE, ref)
        except Exception:
            return None

    def delete(self, ref: str) -> None:
        try:
            self._keyring().delete_password(SERVICE, ref)
        except Exception:
            pass


class MemoryStore:
    """Usado nos testes; nada é gravado no sistema."""

    def __init__(self):
        self.values: dict[str, str] = {}

    def set(self, ref: str, secret: str) -> None:
        self.values[ref] = secret

    def get(self, ref: str) -> str | None:
        return self.values.get(ref)

    def delete(self, ref: str) -> None:
        self.values.pop(ref, None)
