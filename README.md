# Monitor

Central de operação pessoal com IA local para reunir demandas, e-mails, acompanhamento comercial, sites, redes sociais e arquivos.

**Estado: Fase 1 em desenvolvimento.** A versão `v0.0.1` registra a especificação inicial. O código atual implementa demandas, persistência, kanban e oito telas. As integrações de e-mail, sites, redes, arquivos e chat ainda são demonstrações. Consulte [validação](docs/VALIDATION.md).

## Objetivo

![Interface atual em modo de demonstração](docs/images/overview.png)

- Monitorar várias caixas de e-mail e sugerir demandas para revisão.
- Criar demandas manualmente e acompanhar a próxima ação comercial.
- Acompanhar disponibilidade dos sites e funcionamento dos formulários.
- Consultar métricas e mensagens de redes sociais por integrações oficiais.
- Catalogar arquivos locais e pastas sincronizadas do OneDrive.
- Conversar com um assistente local que consulta os registros e cita suas fontes.

A IA sugere; ações dependem das regras e confirmações da interface. E-mails não serão enviados, apagados ou movidos nesta primeira linha de desenvolvimento.

## Referências

- [Especificação completa](prompt-codex-monitor.md)
- [Protótipo das telas](<Monitor — Protótipo.pdf>)
- [Fases e critérios de entrega](docs/ROADMAP.md)
- [Notas da primeira release](docs/releases/v0.0.1.md)

O briefing e o PDF são referências de produto, não demonstrações de funcionalidades implementadas. Modelos, métricas e requisitos de provedores deverão ser validados durante a implementação.

## Arquitetura prevista

```text
app/
  backend/       Python 3.12, FastAPI, SQLModel, SQLite, APScheduler
  frontend/      React, Vite, TypeScript
  desktop/       Tauri 2 e sidecar Python
relay/           Serviço de eventos no VPS, FastAPI e Docker
scripts/         Build Windows, avaliações e ferramentas futuras
docs/            Planejamento e documentação
```

Backend, frontend e desktop contêm a implementação inicial. O relay permanece reservado para a Fase 4.

O aplicativo será instalável no Windows. O Ollama executará a IA no PC; o relay receberá eventos enquanto o PC estiver desligado. Monitoramento externo deverá detectar indisponibilidade do próprio VPS.

Dados ativos ficarão fora de pastas sincronizadas. Credenciais serão mantidas no gerenciador de credenciais do sistema; backups poderão ir para o OneDrive. O modelo local será configurável e testado no hardware disponível, sem promessa prévia de desempenho ou precisão.

## Desenvolvimento

Requisitos Windows: Node 22+, Python 3.12, Rust estável, C++ Build Tools e WebView2 ([pré-requisitos Tauri](https://v2.tauri.app/start/prerequisites/)).

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -c app/backend/requirements-dev.lock -e 'app/backend[dev]'
npm ci
npm run tauri -- dev
```

O Tauri inicia o backend automaticamente. `MONITOR_PYTHON` permite indicar outro interpretador. Para dados fictícios, defina `$env:MONITOR_DEMO='1'` antes de abrir. Banco real em `%LOCALAPPDATA%\Monitor\monitor.db`; demo em `demo.db`, separado. Dados ativos não ficam no OneDrive.

`npm run dev` inicia apenas uma prévia no navegador. Clique em **Explorar demonstração**; alterações nessa prévia ficam em memória e se perdem ao recarregar. A prévia não acessa o banco real.

```powershell
.venv/Scripts/python.exe -m pytest app/backend/tests
npm test
npm run build
./scripts/build_windows.ps1 -Python .venv/Scripts/python.exe
```

O script gera o sidecar com PyInstaller, testa o executável e compila os instaladores NSIS/MSI em `dist/`. O workflow Windows desktop faz o mesmo no GitHub Actions. Os instaladores desta etapa não têm assinatura Authenticode nem atualizador ativo.

Para validação sem ativar inicialização automática, execute o binário com `--no-autostart`. O instalador MSI usa a versão interna numérica `0.1.0.1`, correspondente à versão alpha do produto.

Ollama é separado do instalador. Nas configurações, verifique a disponibilidade, ajuste o modelo e solicite seu download. O padrão do briefing é configurável e precisa ser validado no hardware. Nenhum chat ou análise real de e-mail está ativo nesta fase. Credenciais IMAP virão na Fase 2; backup e catálogo do OneDrive na Fase 5.

## Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Relatos de problemas e propostas de melhoria são bem-vindos. Use apenas dados fictícios em exemplos.

## Licença

[MIT](LICENSE). Componentes e modelos de terceiros permanecem sujeitos às respectivas licenças. O projeto não é afiliado à Meta, Microsoft ou aos fornecedores citados.
