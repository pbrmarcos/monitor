# Validação

Situação em 12/11/2026, versão `0.2.0-alpha.1` (Fases 1 e 2 e pasta de arquivos). Sites, redes sociais, catálogo de arquivos e chat não estão conectados; as telas mostram “Em breve” ou dados de demonstração.

## O que foi executado nesta versão

| Verificação | Resultado |
|---|---|
| `pytest app/backend/tests` | 22 testes passaram |
| `npm test` (componentes) | 2 testes passaram |
| `scripts/keyring_smoke.py` | passou no cofre do Windows: escrita, leitura e remoção de credencial sintética |
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

## Validação externa e pendências

O [build final de 4359a07](https://github.com/pbrmarcos/monitor/actions/runs/43239428556) passou com testes, sidecar, frontend, Rust e instaladores NSIS/MSI. Os pacotes da release `v0.2.0-alpha.1` são os artefatos dessa execução. Alterações posteriores desta entrega são documentação, o lock gerado pelo próprio build e um filtro no script de empacotamento para excluir instaladores antigos retidos no cache. O código do aplicativo corresponde ao build validado.

- **Interação com o instalador.** A compilação NSIS e MSI passou no [workflow Windows](https://github.com/pbrmarcos/monitor/actions/runs/43238640808), incluindo a página de pasta e o plugin de diálogo. Falta conferir a interação manual com essa página. O MSI não tem essa página; nele a pasta é escolhida no aplicativo.
- **Código Rust.** A compilação passou no CI; o `Cargo.lock` resolvido pelo build foi recuperado para versionamento. A validação de interação com as funções nativas continua pendente.
- **Contas IMAP reais.** A coleta só rodou contra o servidor falso. Falta testar com as quatro caixas, incluindo certificados, pastas e volume real.
- **Credenciais reais.** A suíte usa cofre em memória. O teste separado `scripts/keyring_smoke.py` confirmou escrita, leitura e remoção no cofre real do Windows com uma credencial sintética temporária. Nenhuma senha real foi usada.
- **Ollama real.** A chamada com saída estruturada foi testada com transporte simulado. Nenhum modelo foi baixado ou medido.
- **Janela, bandeja, instância única e autostart** continuam pendentes desde a Fase 1.

## Pendências que dependem do Marcos

- Instalar o `.exe` gerado pelo workflow e conferir a página de pasta.
- Dados das contas: servidor IMAP, porta, usuário e senha de cada frente.
- Instalar o Ollama e baixar o modelo; depois rotular um CSV de e-mails reais e rodar `scripts/eval_emails.py`.

## Revisão de continuidade

Foram adicionadas regressões para filas IMAP acima de 200 mensagens, coleta parcial, prazos relativos a mensagens antigas, correções durante a chamada ao modelo, retirada de sugestões rebaixadas, senhas em respostas de validação e fórmulas em CSV. O cofre real do Windows foi testado somente com uma credencial sintética temporária, removida ao final. Nenhuma conta real foi acessada.
