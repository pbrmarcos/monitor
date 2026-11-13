"""Backend real para integração, com cofre em memória e sem credenciais pessoais."""
from monitor import main
from monitor.secrets_store import MemoryStore

main.KeyringStore = MemoryStore
main.run()
