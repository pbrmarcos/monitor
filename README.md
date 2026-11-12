# Monitor

Central de operação pessoal com IA local para reunir demandas, e-mails, acompanhamento comercial, sites, redes sociais e arquivos.

**Estado: especificação e planejamento. Ainda não há aplicativo funcional ou instalador.** A versão `v0.0.1` registra o início público do projeto; nenhuma integração está implementada.

## Objetivo

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

Essas pastas estão reservadas para implementação; não contêm aplicações executáveis nesta versão.

O aplicativo será instalável no Windows. O Ollama executará a IA no PC; o relay receberá eventos enquanto o PC estiver desligado. Monitoramento externo deverá detectar indisponibilidade do próprio VPS.

Dados ativos ficarão fora de pastas sincronizadas. Credenciais serão mantidas no gerenciador de credenciais do sistema; backups poderão ir para o OneDrive. O modelo local será configurável e testado no hardware disponível, sem promessa prévia de desempenho ou precisão.

## Desenvolvimento

A Fase 1 ainda não foi iniciada. Não há comandos de execução, testes ou build disponíveis. As instruções de instalação serão adicionadas quando houver código validado; não há necessidade de fornecer credenciais para examinar este repositório.

## Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Relatos de problemas e propostas de melhoria são bem-vindos. Use apenas dados fictícios em exemplos.

## Licença

[MIT](LICENSE). Componentes e modelos de terceiros permanecem sujeitos às respectivas licenças. O projeto não é afiliado à Meta, Microsoft ou aos fornecedores citados.
