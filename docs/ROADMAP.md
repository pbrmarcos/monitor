# Roteiro de entrega

A Fase 1 está em desenvolvimento; as demais estão pendentes. A release v0.0.1 registra a especificação inicial, anterior ao código. Consulte `VALIDATION.md` para validação e pendências.

| Fase | Escopo | Critério de entrega |
|---|---|---|
| 1 | Base desktop | Monorepo, persistência e migrações, oito telas, CRUD de demandas, kanban, Tauri e sidecar, bandeja e instalador Windows validados |
| 2 | E-mails | IMAP somente leitura, keyring, fila de IA, regras, sugestões e avaliação com dados rotulados |
| 3 | Lembretes | Agendamento persistente, notificações e resumo diário |
| 4 | Sites e relay | Formulários persistidos, deduplicação, verificações, incidentes e monitor externo |
| 5 | Arquivos | Catálogo do OneDrive, extração, busca e backup consistente do banco |
| 6 | Assistente | Consultas ao banco, fontes citadas e confirmação de ações |
| 7 | Redes sociais | Provedores oficiais, snapshots, mensagens e Discord opcional |

## Antes de considerar uma fase concluída

- Executar os testes relevantes e registrar os resultados.
- Atualizar instruções, limitações e requisitos de configuração.
- Separar dados de demonstração de integrações reais.
- Informar dependências externas e aprovações pendentes.

## Decisões a validar

- Disponibilidade da tag do modelo Ollama e consumo real de memória na GPU de 6 GB.
- Requisitos e permissões das contas profissionais da Meta.
- Capacidade do VPS e estratégia de operação enquanto o PC estiver desligado.
- Monitoramento externo independente do VPS.
- Empacotamento e ciclo de vida do backend no Windows.

O critério de 95% de recall em e-mails importantes é uma meta de avaliação, não um resultado medido ou uma garantia.
