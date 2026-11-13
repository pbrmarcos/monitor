# Validação

Situação em 13/11/2026, versão `0.10.0-alpha.1`. O histórico abaixo separa testes simulados, verificações reais e validações manuais ainda pendentes.

## Imagens, registros e skills (0.10.0-alpha.1)

146 testes de backend e 22 de interface passaram localmente; TypeScript/Vite compilou. A cobertura inclui autenticação do visualizador, persistência das métricas por resposta, limpeza dos logs sem apagar métricas do chat, exclusão da conversa, retenção limitada, recuperação de registros interrompidos, ferramentas locais sem métricas inventadas e skills selecionáveis com limites de tamanho e quantidade.

O teste visual com dados fictícios passou em 1400, 860 e 600 px, incluindo abertura de imagem enviada, zoom, Esc, métricas e novas abas, sem erros de página ou transbordamento horizontal. No teste integrado com API, SQLite e Ollama reais, o Qwen3.5 4B Q4_K_M leu corretamente uma imagem sintética com valor e prazo; as métricas foram persistidas e o visualizador recuperou a imagem. Foram observados 75,49 tokens/s de geração; a chamada total levou 7,36 s, incluindo 6,01 s de carga do modelo. Isso não é uma garantia de desempenho nem uma avaliação geral de qualidade.

Mantido o modelo escolhido para a GPU de 6 GB. As skills são instruções locais, não treinamento dos pesos nem carregamento de modelos extras. O teste do executável empacotado também passou a verificar registros de ações, cadastro/desativação de skill e recuperação de imagem. A validação do novo instalador é feita pelo workflow Windows da release.

## Interface e datas de e-mails (0.9.1-alpha.1)

135 testes de backend passaram. As alterações do Antigravity no commit 1244e29 também passaram pela compilação TypeScript/Vite e pelos 17 testes de componentes. O novo caso verifica a extração da data escrita no trecho literal citado pela IA, mantendo uma renovação informativa como informativa.

A versão foi incrementada para publicar as alterações num novo instalador; o commit sozinho não substitui o aplicativo instalado. Aplicativo, frontend, backend e pacote Python foram alinhados em 0.9.1-alpha.1 (Python 0.9.1a1; MSI 0.9.1.1). A conferência do atualizador consulta a release fixa `updates`; a versão instalada só muda depois da instalação e da reabertura do aplicativo.

O [build Windows de 7505b1f](https://github.com/pbrmarcos/monitor/actions/runs/43473193612) passou com 135 testes de backend, 17 de interface, backend empacotado, scheduler, Chrome, carregamento do motor de voz, leitura de PDF/Word, frontend, Rust, instaladores NSIS/MSI e assinaturas do atualizador. O manifesto público foi consultado sem autenticação e anuncia 0.9.1-alpha.1; os dois instaladores responderam à consulta de disponibilidade. A instalação efetiva e a mudança do número no aplicativo instalado ainda exigem validação manual.

## Respostas aprendidas, anexos e voz (0.9.0-alpha.1)

Em 13/11/2026: 134 testes de backend e 17 de componentes passaram; TypeScript e Vite compilaram; o teste visual e o integrado (API e SQLite reais, Ollama real) passaram. Funcionamento e limites em [RESPOSTAS.md](RESPOSTAS.md) e [ANEXOS-E-VOZ.md](ANEXOS-E-VOZ.md).

- **Aprendizado de estilo e respostas.** Testado com servidor IMAP simulado: primeira coleta limitada aos 100 mais recentes, leitura da pasta de enviados só com `EXAMINE` e `BODY.PEEK` (sem escrita), perfil por conta, preservação de perfil editado, duas respostas por e-mail, duas versões de um trecho, rascunho salvo, remoção dos dados com a conta. Com o `qwen3.5:4b` real, a descrição do estilo saiu coerente e as respostas imitaram saudação, despedida e tamanho; o modelo às vezes assume um prazo que o usuário não deu, por isso o texto avisa para revisar.
- **Anexos.** Leitura de texto, PDF, Word, Excel e imagem, recusas com mensagem (executável, `.doc`, arquivo vazio, binário, PDF quebrado, acima de 10 MB), conteúdo entregue ao modelo uma vez e mantido no histórico, imagem só no turno em que foi enviada, limites por mensagem, expiração de anexos não enviados e instruções dentro de arquivos sem efeito (nenhuma regra ou lembrete é criado). Com o modelo real: um print de conversa fictício foi lido (valor pedido e prazo corretos) e respondido no formato Situação, Opção 1 e Opção 2; um arquivo de texto anexado pela interface foi lido e respondido corretamente.
- **Voz.** Testado com motor e repositório de modelos simulados: download com SHA-256 conferido, retomada de download interrompido, modelo corrompido recusado, rede fora do ar, motor ausente, limites de áudio, descarga por inatividade e erros sem detalhes internos. **Nenhuma transcrição com modelo e fala reais foi feita**, e nenhum modelo foi baixado.
- **Defeito encontrado no executável empacotado.** O backend desktop é iniciado com um pipe na entrada padrão e uma leitura bloqueada nele travava o carregamento das bibliotecas nativas do Whisper (só no executável e no modo do aplicativo). A espera pelo encerramento do aplicativo passou a consultar o pipe sem bloquear. Há teste automatizado que falha com o comportamento antigo, e `scripts/voice_sidecar_smoke.py` confirma no executável compilado que o motor carrega (com modelo falso, sem baixar nada) e que PDF e Word são lidos.
- **Tamanho.** O executável do backend passou de 22 MB para cerca de 136 MB com Whisper, bibliotecas de áudio e PDF.
- **Não validado:** transcrição real, permissão e gravação do microfone no aplicativo instalado, arrastar arquivo do Explorer para a janela instalada e contas IMAP reais.

O [build Windows da 0.9.0-alpha.1](https://github.com/pbrmarcos/monitor/actions/runs/43407857797) passou e publicou os instaladores com as dependências de voz e anexos.

## Ações reais pelo chat (0.8.0-alpha.1)

As ações têm interpretação determinística de pedidos diretos e confirmação do banco. Os testes reproduzem o formato do pedido da imagem com um título sintético, guardam o lembrete no horário correto de São Paulo e verificam que o envio ao Google é marcado como pendente quando a conta não está conectada. Criar, reagendar, concluir e cancelar são testados sem chamar o Ollama. Demandas são criadas com frente explícita ou selecionada; mudança de etapa, prioridade e data usam o identificador do registro.

A suíte de backend passou com 107 testes, além dos 7 testes de componentes, TypeScript/Vite e da navegação em três larguras. Os casos cobrem dados faltantes completados em outra mensagem, cancelamento de pedido pendente, datas e horários inválidos/passados, referência a registro inexistente, duplicação por repetição, troca de conversa, mensagens encaminhadas e saída do modelo sem autoridade para executar ações. Um novo título explícito substitui o pedido pendente e o modo de demonstração não envia eventos, mesmo com token simulado.

O Google simulado verifica eventos com início, fim e fuso, duração, repetição idempotente, reagendamento, cancelamento e serviço ocupado/indisponível sem falsa confirmação. Uma sincronização antiga não confirma um novo horário ainda não enviado. Nenhum evento foi criado numa conta Google real.

A integração pela interface usou HTTP, SQLite e o scheduler reais com um cofre em memória: criou o lembrete no chat, abriu pela confirmação, recarregou a tela, verificou persistência e concluiu por outro pedido no chat. A captura foi inspecionada. Em teste separado com Qwen real e banco isolado, a conversa geral identificou corretamente o título e o horário confirmados pela ação anterior. Isso não é uma estimativa de precisão de linguagem natural.

Identificadores de demandas e lembretes não são reutilizados após exclusão; a migração mantém os registros existentes e os testes cobrem bancos antigos. Uma referência histórica a uma demanda excluída não pode alterar outra demanda recém-criada. Excluir a conversa mantém os registros criados e remove o histórico de mensagens e ações dessa conversa.

O [build Windows de 71dae0b](https://github.com/pbrmarcos/monitor/actions/runs/43347321949) passou com os testes, a criação de um lembrete pelo chat no backend empacotado, scheduler, Chrome, frontend, Rust, instaladores NSIS/MSI e assinaturas do atualizador. Os pacotes 0.8.0-alpha.1 são os artefatos dessa execução. A instalação efetiva pelo botão continua pendente de validação manual no aplicativo instalado.

## Instagram pelo Chrome oculto (0.7.0-alpha.1)

82 testes de backend e 6 de interface passaram, além de TypeScript/Vite e navegação visual em três larguras. O novo fluxo de conexão, pausa e revisão de comentários foi testado com a API simulada; a tela foi inspecionada em 1600 e 820 px com dados fictícios.

Os testes do backend cobrem descoberta e conexão sem token, rejeição de perfil inexistente/duplicado, criação automática apenas de pedidos comerciais novos, revisão dos antigos, comentários da própria conta ignorados, deduplicação em rodadas e reconexões, criação manual idempotente, pausa, desafio de login, manutenção dos últimos dados, modo de demonstração isolado, paginação, contadores exatos e migração de contas da API preservando sua referência ao cofre.

O teste `run_backend.py --browser-smoke` abriu o Chrome real sem janela e percorreu tanto as respostas da sessão quanto a alternativa pela página. Todas as respostas foram interceptadas com dados sintéticos; nenhum Instagram real foi acessado por esse teste. O mesmo comentário recebeu a mesma identidade nos dois leitores. Esse teste também é executado no backend empacotado pelo build Windows.

A leitura foi exercitada separadamente em três contas reais autorizadas, confirmando totais e leitura das publicações da página. A rota interna de perfil retornou 404, e a alternativa pela página funcionou. Uma quarta conta estava aberta no Prospect e foi adiada, sem encerrar o programa ou seu Chrome. Não foram inseridas demandas de teste no banco real; a criação de demandas foi validada com comentários sintéticos. Uma coleta pontual não demonstra operação contínua por dias nem cobertura de todos os comentários.

A agenda consulta a cada 15 minutos enquanto PC e Monitor estão ativos; perfis ocupados são adiados. Login pendente e limite de consultas exigem intervenção do usuário antes da retomada. Direct e stories não são lidos pelo navegador. A instalação efetiva pelo atualizador continua pendente de validação manual no aplicativo instalado.

O [build Windows de 015e888](https://github.com/pbrmarcos/monitor/actions/runs/43332834554) passou com os testes, backend empacotado, scheduler, os dois leitores do Instagram em Chrome real sem janela com respostas sintéticas, frontend, Rust, instaladores NSIS/MSI e assinaturas do atualizador. Os avisos do Playwright e do Node acompanham a distribuição. Os pacotes 0.7.0-alpha.1 são os artefatos dessa execução.

## Conversas salvas e memórias verificáveis (0.6.0-alpha.2)

62 testes de backend e 5 de componentes passaram, com TypeScript/Vite, navegação visual em três larguras e integração real de API/SQLite. Os casos novos cobrem reinício, separação por modo, exclusão durante geração, bloqueio de duas respostas simultâneas na mesma conversa, persistência de erros e recusa de regras emitidas pelo modelo em perguntas comuns. Uma preferência apagada não volta ao contexto pela antiga mensagem de aprendizado.

Os identificadores das conversas não são reutilizados após exclusão: uma resposta ainda em andamento não pode cair numa conversa nova. A migração das tabelas do protótipo preserva os registros existentes; o teste parte de um banco antigo, migra, exclui e cria outra conversa para conferir essa garantia.

O Qwen local foi exercitado com perguntas comuns e um pedido explícito de preferência. A pergunta sobre a capital da Austrália não criou memória; o pedido de duas frases foi salvo uma única vez; a resposta seguinte teve duas frases, sem marcadores internos. Isso é validação pontual de funcionamento, não estimativa de precisão nem treinamento dos pesos do modelo.

A integração pelo navegador criou uma conversa de trabalho com o modelo real, reabriu após recarregar, guardou uma regra manual e excluiu a conversa. O teste não usou contas reais de e-mail, Google ou Instagram.

O script `browser_profile_probe.mjs` passou com Chrome real em modo sem janela, perfil temporário e cookie sintético persistente após reinício. Nenhuma sessão pessoal ou conta real foi acessada. O [estudo do navegador](ESTUDO-REDES-NAVEGADOR.md) diferencia essa prova da coleta efetiva de Instagram, ainda não implementada.

O [build Windows de 1ab4c0c](https://github.com/pbrmarcos/monitor/actions/runs/43322313518) passou com os testes, sidecar empacotado, scheduler, frontend, Rust, instaladores e assinaturas do atualizador. O teste do sidecar também cria, consulta e exclui conversas e preferências. Os pacotes 0.6.0-alpha.2 são os artefatos dessa execução. A instalação efetiva pelo botão continua pendente de validação manual no aplicativo instalado.

## Versão e atualizações em destaque (0.5.4-alpha.1)

O painel foi movido para o início das Configurações. O novo teste simula a versão nativa diferente da versão do backend e verifica a preferência pela versão do aplicativo, a consulta apenas após clique, o estado atualizado e a detecção de nova versão sem instalar automaticamente. O botão de consulta permanece disponível após encontrar uma atualização.

Os cinco testes de componentes, TypeScript/Vite e a navegação visual em três larguras passaram. As chamadas nativas são simuladas nos testes; a execução do instalador pelo botão continua pendente de validação manual no aplicativo instalado.

O [build Windows de 2032b18](https://github.com/pbrmarcos/monitor/actions/runs/43310916978) passou com os testes, sidecar, scheduler, frontend, Rust, instaladores e assinaturas do atualizador. Os pacotes 0.5.4 são os artefatos dessa execução.

## Conversa geral e assistente de trabalho (0.5.3-alpha.1)

O teste da API bloqueia explicitamente a coleta de contexto comercial durante uma conversa geral e confere o conteúdo enviado ao Ollama simulado, com o histórico fornecido pelo usuário. O modo padrão continua sendo o de trabalho, preservando os clientes anteriores e as fontes dos registros.

Quatro testes de componentes passaram; o novo teste confere o modo e o histórico enviados em cada tela e a limpeza independente. A verificação no navegador alternou entre as duas conversas, limpou a geral e confirmou a permanência da conversa de trabalho, mantendo os balões compactos em três larguras. TypeScript/Vite compilou. Os históricos são de sessão; o modelo recebe as mensagens recentes de cada conversa.

O [build Windows de 664a796](https://github.com/pbrmarcos/monitor/actions/runs/43307550998) passou com os testes, sidecar, scheduler, frontend, Rust, instaladores e assinaturas do atualizador. Os pacotes 0.5.3 vêm dessa execução; a instalação pelo botão continua pendente de validação manual.

## Favicons das empresas (0.5.2-alpha.1)

Upload PNG e ICO exercitado pela interface com API e SQLite temporários reais. A integração verificou os dois ícones após recarregar, sua presença nas abas de sete telas, normalização em 64 pixels, proporção e transparência. A leitura usa data URI, compatível com a política de imagens do desktop. A navegação visual em três larguras e os três testes de componentes passaram.

A API foi testada para persistência após reinício, remoção, rejeição de formatos/dimensões/tamanhos inválidos e preservação dos ícones quando clientes antigos salvam preferências sem esse campo. Os testes de preferências/Instagram usam cofre em memória, sem alterar credenciais reais.

O [build Windows de b58e05a](https://github.com/pbrmarcos/monitor/actions/runs/43303698991) passou com os testes, sidecar, scheduler, frontend, Rust, instaladores e assinaturas do atualizador. Os pacotes 0.5.2 vêm dessa execução. A instalação pelo botão continua pendente de validação manual.

## Altura das mensagens do assistente (0.5.1-alpha.1)

As mensagens da IA usavam a classe `assistant`, compartilhada com o painel lateral de altura `100vh`. As classes dos balões agora têm o prefixo `message-`, preservando a altura definida pelo conteúdo e o alinhamento das mensagens do usuário.

TypeScript/Vite e a verificação visual passaram. O smoke test mediu a altura dos balões em relação ao texto, nas larguras 820, 1600 e 2560, tanto na visão geral quanto na tela Assistente, além da navegação habitual. A verificação usa a resposta de demonstração; a correção é no layout compartilhado, sem alterar a chamada à IA.

O [build Windows de 63cc702](https://github.com/pbrmarcos/monitor/actions/runs/43286144318) passou com os testes, sidecar, scheduler, frontend, Rust, dois instaladores e assinaturas do atualizador. Os pacotes da release 0.5.1 vêm dessa execução; a instalação efetiva pelo botão continua pendente de validação manual no Windows.

## Assistente, Google Agenda e ajustes de uso (0.5.0-alpha.1)

Em 12/11/2026: 46 testes de backend e 3 de componentes passaram; TypeScript e Vite compilaram. O teste visual arrasta um cartão do kanban para outra coluna com o ponteiro, confere que soltar não abre os detalhes e que, em 2560 px, o conteúdo ocupa toda a área entre o menu e o assistente.

- **Ollama real.** Com `qwen3.5:4b-q4_K_M` instalado neste computador, a análise de e-mail e o chat responderam. A primeira chamada levou cerca de 170 s (carga do modelo); as seguintes, 3 s na análise e 1,4 s no chat, com 3,2 GB de VRAM. Num único e-mail de teste o modelo marcou “precisa de ação”, mas classificou um pedido de orçamento como informativo e não extraiu a data; as regras determinísticas cobrem esse caso. A qualidade ainda precisa ser medida com e-mails reais rotulados.
- **Assistente.** Os testes conferem que o contexto enviado contém as demandas abertas com frente e prazo, exclui demandas encerradas e nunca inclui senhas; cobrem Ollama fora do ar, modelo ausente e o parâmetro `think` recusado.
- **Google Agenda.** Testado com um Google simulado: autorização com PKCE e `state`, token só no cofre, criação, atualização, recriação de evento apagado, remoção ao encerrar a demanda, repetição sem chamadas quando nada mudou, acesso revogado e modo de demonstração sem tráfego. **Nenhuma conta Google real foi conectada.**
- **Personalização.** Os testes cobrem perfil, nomes das frentes e cores, incluindo a recusa de cor principal clara, de imagem que não seja PNG/JPEG/WebP e de frente sem nome. O teste integrado troca o nome de uma frente, o perfil e a paleta pela interface e confere que persistem após recarregar. O nome novo da frente chega ao contexto do assistente.
- **Instagram.** Testado com um Instagram simulado: token só no cofre, foto copiada para o banco, totais, posts, curtidas e comentários da semana, variação de seguidores contra a coleta de 7 dias antes, stories indisponíveis mostrados como ausentes, token expirado e modo de demonstração sem tráfego. **Nenhum perfil real foi conectado**; os nomes dos campos da API vêm da documentação da Meta e não foram conferidos contra o serviço.
- **Atualização pelo aplicativo.** Com autorização explícita do usuário, a chave existente foi cadastrada no segredo protegido do GitHub, sem entrar no repositório. O [build Windows de 15c3903](https://github.com/pbrmarcos/monitor/actions/runs/43280202593) passou com 46 testes de backend, 3 de componentes, sidecar, scheduler, frontend, Rust e instaladores. Gerou duas assinaturas e publicou a release e o manifesto `latest.json` do canal `updates`. O `Cargo.lock` resolvido pelo build foi recuperado e versionado; os pacotes distribuídos são os artefatos dessa execução.
- **Não validado:** instalação efetiva pelo botão do atualizador, preservação de dados nessa instalação e demais interações nativas no aplicativo instalado. Google Agenda e Instagram ainda dependem de validação com contas reais.

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

O [build Windows de 50bffd2](https://github.com/pbrmarcos/monitor/actions/runs/43258676038) passou nos testes, empacotamento do sidecar, smoke tests do executável, scheduler com fuso, frontend, Rust e geração dos instaladores NSIS/MSI. Os pacotes `v0.4.0-alpha.1` vêm dessa execução. As alterações posteriores são documentação; o código distribuído corresponde ao build validado. A interação manual com recursos nativos continua pendente.

Consultas públicas pontuais: Carteira Pronta, WebQ e Nextlink responderam HTTP 200; o endereço Rocha Comercial sem `www` respondeu 200, enquanto a versão com `www` falhou na resolução de DNS nesta consulta. Isso é uma observação local, não uma medição de disponibilidade contínua ou falha universal de DNS.

Docker e PHP não estão instalados no ambiente local. O [CI do relay](https://github.com/pbrmarcos/monitor/actions/runs/43258419624) construiu e executou a imagem Linux com usuário sem privilégios e volume persistente, verificou recebimento, repetição segura, reinício, recuperação da fila e ACK. A sintaxe da função auxiliar passou no PHP 8.3; sua adaptação a um handler real continua pendente. O teste de prontidão foi ajustado para repetir conexões reiniciadas enquanto o contêiner sobe.

Implantação no Coolify, adaptação dos handlers, coleta com formulários reais, monitor externo, métricas do host e teste sintético semanal permanecem pendentes. O código não altera os sites existentes nem publica o relay.

## Revisão de continuidade

Foram adicionadas regressões para filas IMAP acima de 200 mensagens, coleta parcial, prazos relativos a mensagens antigas, correções durante a chamada ao modelo, retirada de sugestões rebaixadas, senhas em respostas de validação e fórmulas em CSV. O cofre real do Windows foi testado somente com uma credencial sintética temporária, removida ao final. Nenhuma conta real foi acessada.
