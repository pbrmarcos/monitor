# Validação da base desktop

Fase 1 em andamento. E-mails, sites, redes, arquivos e chat não estão conectados. As respectivas telas exibem avisos de demonstração ou fase futura.

## Verificações

Validação local em 12/11/2026: 5 testes backend e 2 testes de componentes passaram; TypeScript/Vite compilou; teste visual de criação/edição e viewport compacto passou; sidecar empacotado passou incluindo encerramento pelo pipe do processo pai. Auditoria npm: zero vulnerabilidades no conjunto instalado. Ollama foi testado com transporte simulado (status, configuração, progresso e indisponibilidade); nenhum modelo foi baixado.

O teste integrado também passou com frontend, HTTP e SQLite reais: criação, recarga da tela, persistência e consulta do histórico. Somente a camada IPC nativa é simulada nesse teste; ele não substitui a validação da janela Tauri.

- Backend: autenticação, campos inválidos, data de retorno obrigatória, CRUD, histórico, persistência e separação do banco de demonstração.
- Frontend: oito telas, filtro por frente e validação de formulário.
- Teste visual: criação e edição, acompanhamento com data e viewport compacto.
- Sidecar: handshake, API autenticada e banco local por executável PyInstaller.
- Auditoria npm após atualização das ferramentas de teste.
- CI Windows: testes, empacotamento e compilação Rust/Tauri. Conferir resultado antes de publicar instalador.

## Pendências para concluir a Fase 1

O workflow Windows passou para o commit `b95c6a9`: compilação Rust/Tauri e geração de NSIS e MSI concluídas. A versão MSI numérica foi definida explicitamente como `0.1.0.1`. Os ajustes posteriores passam por novo build antes da publicação da alpha.

- Validar instalador, janela, bandeja, instância única e autostart numa sessão Windows.
- Validar recuperação da queda do backend na sessão desktop (a interface já aguarda o endpoint de saúde e escuta o reinício).
- Testar download do modelo explicitamente escolhido no hardware alvo.
- Indicador de alerta e pausa de workers dependem dos workers das próximas fases; o menu identifica a indisponibilidade nesta etapa.
- Notificações com navegação e atualização assinada não estão ativas.

Nenhuma conta ou credencial real é necessária nesta fase.
