# Atualização pelo aplicativo

Em **Configurações › Aplicativo › Verificar atualizações**, o Monitor consulta o GitHub, baixa o instalador da versão nova, confere a assinatura, fecha, instala e abre de novo. Dados, credenciais e a pasta de arquivos são mantidos.

A versão `0.5.0-alpha.1` é a primeira com esse botão. Quem tem uma versão anterior precisa instalar esta uma última vez pelo instalador.

## Como funciona

- Cada instalador é assinado no build com uma chave privada. O aplicativo traz a chave pública e recusa qualquer pacote sem assinatura válida.
- O aplicativo lê o manifesto `latest.json`, publicado na release fixa `updates` do repositório. O manifesto aponta para o instalador da versão mais recente.
- O instalador roda em modo passivo: mostra só a barra de progresso e não pergunta de novo a pasta de arquivos.
- Antes de copiar os arquivos, o instalador encerra o processo `monitor-backend.exe`.

## Configuração única

1. A chave privada foi gerada neste computador em `C:\Users\marco\.tauri\monitor-updater.key` (sem senha). **Guarde uma cópia em local seguro**: sem ela não é possível publicar atualizações para quem já instalou. Ela nunca deve entrar no repositório.
2. Cadastre a chave como segredo do repositório no GitHub (Settings › Secrets and variables › Actions › New repository secret), com o nome `TAURI_SIGNING_PRIVATE_KEY` e o conteúdo do arquivo. Pela linha de comando:

   ```powershell
   gh secret set TAURI_SIGNING_PRIVATE_KEY --repo pbrmarcos/monitor < $env:USERPROFILE\.tauri\monitor-updater.key
   ```

Sem o segredo, o build continua gerando os instaladores, mas sem assinatura e sem manifesto; o botão responde que não há atualização.

## Publicar uma versão

1. Atualize a versão em `tauri.conf.json`, `Cargo.toml`, nos `package.json`, em `pyproject.toml` e em `main.py`, e escreva `docs/releases/vX.Y.Z.md`.
2. Crie e envie a tag: `git tag vX.Y.Z` e `git push origin vX.Y.Z`.
3. O workflow **Windows desktop** compila, cria a release da tag com os instaladores e substitui o `latest.json` da release `updates`.

A partir daí, o botão encontra a versão nova nos computadores instalados.

## Limites

- Nada disso foi executado ainda: a compilação com o plugin de atualização, a assinatura, a publicação e a instalação pela atualização só podem ser conferidas no GitHub Actions e no aplicativo instalado.
- Os instaladores não têm assinatura Authenticode; o Windows pode mostrar o aviso do SmartScreen na instalação manual.
- A verificação é manual, pelo botão. O Monitor não procura atualizações sozinho.
