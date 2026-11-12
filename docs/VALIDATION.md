# Validação

Situação em 12/11/2026, versão `0.2.0-alpha.1` (Fases 1 e 2 e pasta de arquivos). Sites, redes sociais, catálogo de arquivos e chat não estão conectados; as telas mostram “Em breve” ou dados de demonstração.

## O que foi executado nesta versão

| Verificação | Resultado |
|---|---|
| `pytest app/backend/tests` | 15 testes passaram |
| `npm test` (componentes) | 2 testes passaram |
| `tsc --noEmit` | sem erros |
| `scripts/ui_smoke.mjs` (prévia, Edge headless) | passou: sugestão, criação, edição, e-mails, oito telas, larguras de 820, 1600 e 2560 px, nenhum texto abaixo de 11 px |
| `scripts/integration_smoke.mjs` (API e SQLite reais, IPC simulado) | passou: criação, persistência, histórico, pasta de arquivos e backup |
| Sidecar PyInstaller com `keyring` e `APScheduler` + `scripts/desktop_smoke.py` | passou: handshake, autenticação, criação e banco local |
| `scripts/eval_emails.py docs/eval-exemplo.csv --so-regras` | executa; os 5 exemplos são fictícios e não medem qualidade real |

Cobertura dos testes de backend:

- Demandas: autenticação, validação, data de retorno, histórico, persistência, banco de demonstração separado.
- E-mails: coleta por servidor IMAP falso com `EXAMINE` e `BODY.PEEK` e nenhum comando de escrita; senha fora do banco e das respostas; remoção de assinatura; deduplicação; remoção de conta.
- Regras e prazos: “sexta”, “amanhã”, “até dia 15”, “semana que vem”, datas por extenso; orçamento, remetente prioritário, cliente com demanda aberta, publicidade, confiança baixa e prazo inventado pela IA.
- Fila da IA: Ollama fora do ar mantém a fila; JSON inválido gera nova tentativa; correções do usuário entram como exemplos; credenciais nunca vão no prompt.
- Pasta de arquivos: validação do caminho, estrutura, backup pela API do SQLite, exportação CSV, escolha do instalador como padrão.
- Migração de um banco da Fase 1 para o esquema atual.

## O que não foi validado

- **Instalador com a página “Pasta de arquivos”.** O modelo NSIS (`app/desktop/src-tauri/windows/`) não foi compilado: não há Rust nesta máquina e a compilação isolada com NSIS não pôde ser executada. O primeiro build no GitHub Actions é a validação. O MSI não tem essa página; nele a pasta é escolhida no aplicativo.
- **Código Rust.** A inclusão do plugin de diálogo e o `Cargo.lock` serão resolvidos no primeiro build; o `Cargo.lock` versionado ainda não lista `tauri-plugin-dialog`.
- **Contas IMAP reais.** A coleta só rodou contra o servidor falso. Falta testar com as quatro caixas, incluindo certificados, pastas e volume real.
- **Gerenciador de Credenciais do Windows.** Os testes usam um cofre em memória; a gravação real da senha não foi exercitada.
- **Ollama real.** A chamada com saída estruturada foi testada com transporte simulado. Nenhum modelo foi baixado ou medido.
- **Janela, bandeja, instância única e autostart** continuam pendentes desde a Fase 1.

## Pendências que dependem do Marcos

- Rodar o workflow Windows e instalar o `.exe` gerado, conferindo a página de pasta.
- Dados das contas: servidor IMAP, porta, usuário e senha de cada frente.
- Instalar o Ollama e baixar o modelo; depois rotular um CSV de e-mails reais e rodar `scripts/eval_emails.py`.
