# Roteiro de entrega

Situação em 12/11/2026. Detalhes de cada verificação em `VALIDATION.md`; regras de interface em `DESIGN.md`.

| Fase | Escopo | Situação |
|---|---|---|
| 1 | Base desktop: monorepo, banco e migrações, oito telas, demandas, kanban, Tauri e sidecar, bandeja, instalador | Código entregue. Falta validar manualmente instalador, bandeja, instância única e autostart numa sessão Windows |
| 2 | E-mails: IMAP somente leitura, credenciais no Windows, fila de IA, regras, sugestões, correções, avaliação | Código entregue e testado com servidor IMAP e Ollama simulados. Falta validar com contas reais e medir o modelo com e-mails rotulados |
| 2b | Pasta de arquivos: escolha no instalador e nas Configurações, backup diário e exportação | Compilação NSIS/MSI aprovada no CI. Interação manual com a página do instalador pendente |
| 3 | Lembretes: agendamento persistente, notificações do Windows, resumo diário às 7h30 | Agenda, central, resumo e ponte nativa implementados; testes e compilação NSIS/MSI aprovados. Exibição e clique dos avisos no aplicativo instalado pendentes de validação manual |
| 4 | Sites e relay: formulários, deduplicação, verificações, incidentes, monitor externo | Primeira entrega: checagens locais, SSL, incidentes, relay durável, revisão de contatos e deduplicação conservadora. Pendentes implantação real, teste sintético semanal, métricas do host e monitor externo independente |
| 2c | Respostas: estilo aprendido dos enviados, duas sugestões de resposta, melhoria de trecho | Implementado e testado com IMAP simulado e modelo local real. Falta validar com as contas reais |
| 6c | Assistente: anexos, leitura de print de conversa e microfone local | Implementado e testado; transcrição com modelo e fala reais e microfone no aplicativo instalado pendentes |
| 5 | Arquivos: catálogo da pasta, extração de texto, busca, classificação | Pendente (pasta e backup já entregues em 2b) |
| 6 | Assistente: consultas ao banco, fontes citadas e ações | Conversas salvas, preferências, criação de lembretes/demandas, reagendamento, conclusão/cancelamento de lembretes e edição de etapa/prioridade/data de demandas por pedidos diretos. Resultados confirmados pelo banco e atalhos para os registros. Busca em arquivos e novas ferramentas pendentes (`ASSISTENTE.md`) |
| 6b | Google Agenda: demandas com data como eventos na conta do usuário | Implementado e testado com Google simulado. Falta conectar a conta real com a credencial OAuth do usuário (`AGENDA-GOOGLE.md`) |
| 7 | Redes sociais: snapshots, comentários e demandas | Chrome oculto pelos perfis do Prospect, rodadas de 15 minutos, alternativa pela página, revisão de comentários e demandas opcionais por regras. Leitura exercitada em três contas reais; perfil ocupado adiado. Direct, stories pelo navegador, WhatsApp e operação contínua ainda pendentes (`REDES-SOCIAIS.md`) |
| — | Personalização e atualização: perfil, nomes das frentes, cores, atualização pelo aplicativo | Perfil, frentes, favicons e cores entregues. Atualizador compilado, pacotes assinados e manifesto publicado. Instalação pelo botão ainda requer validação manual (`ATUALIZACOES.md`) |

A implementação do navegador deriva do [estudo de coleta em segundo plano](ESTUDO-REDES-NAVEGADOR.md). A conexão anterior pela API continua disponível como alternativa, sem ser requisito do fluxo principal.

## Antes de considerar uma fase concluída

- Executar os testes relevantes e registrar os resultados.
- Atualizar instruções, limitações e requisitos de configuração.
- Separar dados de demonstração de integrações reais.
- Informar dependências externas e aprovações pendentes.
- Conferir as telas novas contra `DESIGN.md`.

## Decisões a validar

- Disponibilidade da tag do modelo Ollama e consumo real de memória na GPU de 6 GB.
- Recall da triagem com e-mails reais rotulados (`scripts/eval_emails.py`). A meta de 95% é um alvo, não um resultado medido.
- Requisitos e permissões das contas profissionais da Meta.
- Capacidade do VPS e operação enquanto o PC estiver desligado.
- Monitoramento externo independente do VPS.

## Diferenças em relação ao briefing

- A pasta de arquivos é escolhida no instalador. O banco em uso continua em `%LOCALAPPDATA%\Monitor`, como o briefing pede; para a pasta vão o backup diário, as exportações e, na Fase 5, os arquivos organizados.
- A coleta de e-mail usa consulta a cada 2 minutos; IDLE não foi implementado.
- Só a caixa de entrada é lida. Outras pastas ficam para quando houver necessidade.
- A criação automática de lembretes para prazos explícitos depende da Fase 3.
- A pedido do usuário, demandas com data são enviadas ao Google Agenda. É o único dado do Monitor que sai do computador, e só depois de a conta ser conectada.
- São sempre quatro frentes; os nomes são editáveis em Configurações.
- A identidade navy/ciano do briefing passou a ser o padrão de uma paleta personalizável, a pedido do usuário.
