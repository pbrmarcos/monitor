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
2. A chave foi cadastrada, com autorização do usuário, no segredo protegido `TAURI_SIGNING_PRIVATE_KEY` do repositório `pbrmarcos/monitor`. Para restaurar a configuração no futuro, use Settings › Secrets and variables › Actions › New repository secret ou a linha de comando, sem imprimir o conteúdo:

   ```powershell
   Get-Content -LiteralPath "$env:USERPROFILE\.tauri\monitor-updater.key" -Raw | gh secret set TAURI_SIGNING_PRIVATE_KEY --repo pbrmarcos/monitor
   ```

Sem o segredo, o build continua gerando os instaladores, mas sem assinatura e sem manifesto; o botão responde que não há atualização.

## Publicar uma versão

1. Atualize a versão em `tauri.conf.json`, `Cargo.toml`, nos `package.json`, em `pyproject.toml` e em `main.py`, e escreva `docs/releases/vX.Y.Z.md`.
2. Crie e envie a tag: `git tag vX.Y.Z` e `git push origin vX.Y.Z`.
3. O workflow **Windows desktop** compila, cria a release da tag com os instaladores e substitui o `latest.json` da release `updates`.

A partir daí, o botão encontra a versão nova nos computadores instalados.

## Limites

- A compilação com o plugin, as duas assinaturas e a publicação do manifesto passaram no [build Windows da versão 0.5](https://github.com/pbrmarcos/monitor/actions/runs/43280202593). A instalação efetiva pelo botão, incluindo fechamento e reabertura e preservação dos dados, ainda exige validação manual no aplicativo instalado.
- Os instaladores não têm assinatura Authenticode; o Windows pode mostrar o aviso do SmartScreen na instalação manual.
- A verificação é manual, pelo botão. O Monitor não procura atualizações sozinho.
