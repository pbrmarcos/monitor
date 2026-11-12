# Validação

Situação em 12/11/2026, versão `0.3.0-alpha.1` (Fases 1 a 3 e pasta de arquivos). Sites, redes sociais, catálogo de arquivos e chat não estão conectados.

## Agenda (Fase 3)

Testes com relógio controlado cobrem fusos, dias úteis, recuperação após reinício, confirmação de encaminhamento, privacidade, reagendamento, cancelamento, demandas encerradas e geração automática de lembretes de e-mail com ativação explícita. A interface permite criar e concluir um lembrete na demonstração. A integração exercita o scheduler de produção, a API e o SQLite com notificações nativas simuladas.

Validação local: 28 testes backend e 3 testes de componentes passaram; TypeScript/Vite compilou. O teste visual passou nas nove telas e em três larguras. O teste integrado criou um lembrete atrasado, aguardou o worker real gerar o aviso e confirmou persistência após recarregar a interface. Nenhum toast real foi enviado nesse teste.

O [build final de 18c4cac](https://github.com/pbrmarcos/monitor/actions/runs/43249286851) passou: testes, sidecar, teste do scheduler dentro do executável, frontend, ponte Rust e instaladores NSIS/MSI. Os pacotes da versão 0.3 vêm dessa execução. Alterações posteriores são documentação e o Cargo.lock resolvido pelo próprio build.

Exibição real de toast, clique e indicador da bandeja ainda exigem validação no aplicativo instalado. O sucesso da chamada ao plugin significa encaminhamento, não prova de leitura pelo usuário. Consulte `AGENDA.md` para funcionamento e limites.

## Verificações anteriores (Fases 1 e 2)

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

## Sites e relay — primeira entrega da Fase 4

Em 12/11/2026: 37 testes de backend e 3 testes de componentes aprovados. A compilação TypeScript/Vite passou. O teste de navegação nas nove telas e três larguras passou; a integração com API, SQLite e scheduler reais incluiu um servidor HTTP temporário para checagens, falha 503, recuperação, pausa, retomada e histórico persistido.

Os testes do relay executam o serviço real com bancos temporários: autenticação por função, validação sem eco de dados, limite de tamanho e taxa, descarte de testes, idempotência, conflito de identificadores, reinício, ACK perdido, commit local antes da confirmação, site sem mapeamento e deduplicação entre canais nos dois sentidos. Tokens são testados com cofre em memória; nenhuma credencial real foi usada.

Consultas públicas pontuais: Carteira Pronta, WebQ e Nextlink responderam HTTP 200; o endereço Rocha Comercial sem `www` respondeu 200, enquanto a versão com `www` falhou na resolução de DNS nesta consulta. Isso é uma observação local, não uma medição de disponibilidade contínua ou falha universal de DNS.

Docker e PHP não estão instalados no ambiente local: o contêiner e a função PHP auxiliar não foram executados aqui. A aplicação FastAPI do relay foi exercitada pelos testes. Implantação no Coolify, adaptação dos handlers, coleta com formulários reais, monitor externo, métricas do host e teste sintético semanal permanecem pendentes. O código não altera os sites existentes nem publica o relay.

## Revisão de continuidade

Foram adicionadas regressões para filas IMAP acima de 200 mensagens, coleta parcial, prazos relativos a mensagens antigas, correções durante a chamada ao modelo, retirada de sugestões rebaixadas, senhas em respostas de validação e fórmulas em CSV. O cofre real do Windows foi testado somente com uma credencial sintética temporária, removida ao final. Nenhuma conta real foi acessada.
