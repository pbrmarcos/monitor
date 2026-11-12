# Validação da base desktop

Fase 1 em andamento. E-mails, sites, redes, arquivos e chat não estão conectados. As respectivas telas exibem avisos de demonstração ou fase futura.

## Verificações

- Backend: autenticação, campos inválidos, data de retorno obrigatória, CRUD, histórico, persistência e separação do banco de demonstração.
- Frontend: oito telas, filtro por frente e validação de formulário.
- Teste visual: criação e edição, acompanhamento com data e viewport compacto.
- Sidecar: handshake, API autenticada e banco local por executável PyInstaller.
- Auditoria npm após atualização das ferramentas de teste.
- CI Windows: testes, empacotamento e compilação Rust/Tauri. Conferir resultado antes de publicar instalador.

## Pendências para concluir a Fase 1

- Validar instalador, janela, bandeja, instância única e autostart numa sessão Windows.
- Validar recuperação da queda do backend e reconexão da interface.
- Testar download do modelo explicitamente escolhido no hardware alvo.
- Indicador de alerta e pausa de workers dependem dos workers das próximas fases; o menu identifica a indisponibilidade nesta etapa.
- Notificações com navegação e atualização assinada não estão ativas.

Nenhuma conta ou credencial real é necessária nesta fase.
