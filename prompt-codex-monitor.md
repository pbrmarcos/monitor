# Projeto: Monitor — central de operação com IA local

Você vai construir o **Monitor**, um software pessoal para um único usuário (Marcos). Ele trabalha sozinho e cuida de **4 frentes de negócio**. Cada frente tem site, formulários, caixa de e-mail e Instagram próprios. Há também 3 números de WhatsApp Business.

O Monitor reúne tudo num painel:
- lê os e-mails e sugere demandas;
- permite criar demandas manualmente;
- acompanha o pipeline comercial;
- verifica se os sites e formulários funcionam;
- mostra números das redes sociais;
- cataloga arquivos;
- oferece um assistente de chat com **IA local**.

Trabalhe em fases (seção 9). Entregue cada fase funcionando, com testes, antes de passar para a próxima.

---

## 1. Ambiente e restrições

- **Máquina principal:** PC Windows com **RTX 3060 de 6 GB**. A IA roda nele via **Ollama**. O modelo padrão é **Qwen3.5 4B quantizado em Q4_K_M** (tag `qwen3.5:4b-q4_K_M`, cerca de 3,3 GB), configurável nas Configurações.
- **Entrega:** o Monitor é um **programa instalável para Windows** (`.exe`/`.msi`), não um script nem um site aberto no navegador (ver seção 2.1).
- **Servidor:** um VPS que já hospeda os 4 sites e os e-mails, gerenciado com **Coolify**. Os e-mails ficam em hospedagem própria e são acessados por **IMAP (993/SSL)**.
- **Arquivos:** OneDrive de 5 TB, sincronizado no PC.
- **Uso:** só o Marcos usa o sistema, sem multiusuário.
- O PC pode estar desligado. Os lembretes continuam valendo e os formulários não podem se perder.
- O VPS pode cair. Por isso, o monitoramento de disponibilidade **não pode depender só do VPS**.

## 2. Arquitetura

Monorepo com duas aplicações:

```
monitor/
  app/        # roda no PC (Windows)
    backend/  # Python 3.12 + FastAPI + SQLModel + SQLite + APScheduler
    frontend/ # React + Vite + TypeScript
    desktop/  # Tauri 2 (src-tauri): janela, bandeja, instalador
  relay/      # roda no VPS (Docker, deploy pelo Coolify)
  docs/
```

### `app` (PC)

- **Backend FastAPI:** escuta apenas em `127.0.0.1`.
- **Banco:** SQLite fora da pasta do OneDrive. Faz backup diário (cópia do `.db`) para uma pasta configurável no OneDrive.
- **Workers com APScheduler, no mesmo processo:**
  - coleta IMAP;
  - fila de análise da IA;
  - verificação dos sites;
  - puxar eventos do relay;
  - lembretes;
  - resumo diário;
  - indexação de arquivos.
- **Fila da IA:** tabela `ai_jobs` com status, processando **um item por vez**. Se o Ollama estiver fora do ar, os itens ficam pendentes e o resto do sistema continua funcionando.
- **Credenciais:** IMAP, tokens etc. ficam no **Windows Credential Manager** via `keyring`. Nunca vão para o banco nem para os logs. **Nunca envie credenciais à IA.**
- **Instalação:** pelo instalador do Windows (seção 2.1). Em desenvolvimento, `npm run tauri dev` sobe a interface e o backend juntos.

### 2.1 Programa desktop (executável)

- **Casca:** **Tauri 2**. A interface React roda numa janela própria (WebView2), sem depender do navegador.
- **Backend como sidecar:** o FastAPI é empacotado com **PyInstaller** num executável único (`monitor-backend.exe`) e registrado como *sidecar* do Tauri.
  - O Tauri inicia o backend ao abrir e o encerra ao sair de vez.
  - Se o processo cair, o Tauri reinicia e registra o erro.
  - O backend escolhe uma porta livre em `127.0.0.1` e a informa ao Tauri. A interface recebe um token de sessão gerado a cada execução, para que outros programas do PC não chamem a API.
- **Bandeja do sistema:**
  - fechar a janela minimiza para a bandeja, e o backend continua trabalhando (e-mails, sites, lembretes);
  - menu da bandeja: Abrir, Nova demanda, Pausar verificações, Sair;
  - o ícone mostra um ponto de alerta quando há site com falha ou prazo vencendo.
- **Iniciar com o Windows:** ativado por padrão e configurável (plugin `autostart`). Inicia minimizado na bandeja.
- **Notificações nativas do Windows** (plugin `notification`). Clicar na notificação abre a tela relacionada.
- **Uma instância só** (plugin `single-instance`). Abrir de novo traz a janela existente para frente.
- **Dados** em `%LOCALAPPDATA%\Monitor\`: banco, logs e configurações. Nunca na pasta do programa nem na do OneDrive.
- **Instalador:** NSIS (`.exe`) e MSI, com ícone, nome "Monitor" e atalho no menu Iniciar. Desinstalar não apaga os dados sem perguntar.
- **Atualizações:** prever o plugin `updater` do Tauri, com assinatura das versões. Pode ficar desativado na primeira versão.
- **Ollama fica fora do instalador**, porque depende do driver da placa de vídeo. O Monitor deve:
  - detectar se o Ollama está rodando (`GET http://127.0.0.1:11434/api/version`);
  - se não estiver instalado, mostrar uma tela de primeiro uso com o link oficial de download;
  - verificar se o modelo `qwen3.5:4b-q4_K_M` existe e oferecer **"Baixar modelo"**, com barra de progresso via `/api/pull`;
  - sem Ollama, todo o resto funciona e os itens ficam na fila da IA.
- **Build:** script `scripts/build_windows.ps1` que gera o sidecar com PyInstaller, compila o frontend e roda `tauri build`. O resultado vai para `dist/`. Opcional: workflow do GitHub Actions (`windows-latest`) que gera o instalador a cada tag.

### `relay` (VPS)

FastAPI pequeno, com SQLite próprio e Dockerfile pronto para o Coolify. Funções:

1. **Receber os envios dos formulários dos 4 sites.**
   - Endpoint: `POST /forms/{site_id}`.
   - Validar o token por site.
   - Aplicar rate limit.
   - Armazenar o envio.
2. **Fila de eventos.** O `app` puxa os eventos novos com `GET /events?after=…`, autenticado por token, e confirma o recebimento.
3. **Lembretes 24 h** (opcional, fase 7): o `app` envia ao relay os lembretes com horário, e o relay dispara o aviso por webhook do Discord quando o PC estiver desligado.

Inclua um snippet de JavaScript para o formulário dos sites. Ele envia para o relay **e mantém o envio atual por e-mail como fallback**.

### Monitor externo

Integre com a API do **UptimeRobot** (chave nas configurações) para ler status, tempo de resposta e histórico vindos de fora do VPS. O `app` também faz suas próprias verificações quando o PC está ligado.

## 3. Modelo de dados (mínimo)

- `fronts`: id, nome, domínio, cor opcional.
- `email_accounts`: id, front_id, endereço, host, porta, usuário, ref_keyring, último UID por pasta, último sync, status.
- `emails`: id, account_id, message_id (único), from, to, subject, date, body_text (truncado), has_attachments, link/UID, imap_flags, status de análise.
- `email_analysis`:
  - email_id;
  - categoria (`orcamento | cliente | financeiro | fornecedor | publicidade | informativo | outro`);
  - importância (`acao | importante | revisar | info`);
  - motivo;
  - resumo;
  - ação sugerida;
  - prazo identificado (texto e data ISO opcional);
  - trecho de origem do prazo;
  - confiança;
  - modelo;
  - correção do usuário.
- `demands`:
  - id, front_id, título, contato, canal (`email | formulario | instagram | whatsapp | manual`), origem_ref;
  - etapa (`novo | qualificacao | preparar_proposta | proposta_enviada | acompanhar | ganho | perdido`);
  - prioridade, prazo, próxima ação, data de retorno, resumo, concluída;
  - created_by (`ia | usuario`).
- `demand_events`: histórico de cada demanda.
- `suggestions`: demandas sugeridas pela IA, aguardando aceitar ou descartar.
- `reminders`: id, demand_id opcional, texto, quando, entregue.
- `sites`: id, front_id, url, texto esperado na página, url do formulário, modo de teste do formulário.
- `site_checks` e `incidents`.
- `files`:
  - caminho local, nome, extensão, tamanho, hash, front_id, cliente, categoria (`proposta | briefing | contrato | material | financeiro | outro`), origem, data;
  - texto extraído (com OCR opcional).
- `social_accounts` e `social_snapshots`: seguidores, posts, engajamento e mensagens pendentes por data.
- `chat_threads` e `chat_messages`, com as fontes citadas em cada resposta.
- `settings`.

## 4. IA local (Ollama)

- **Modelo padrão:** `qwen3.5:4b-q4_K_M`. Guarde o nome do modelo em `settings` e registre em cada análise qual modelo a produziu.
- **Memória da placa:** o modelo ocupa cerca de 3,3 GB dos 6 GB da RTX 3060. Use `num_ctx` de 8192 por padrão (configurável) e `keep_alive` de 10 minutos, para não ocupar a placa o tempo todo.
- **Modo de raciocínio:** nas classificações de e-mail e arquivos, chame o modelo com `think: false`, se o modelo suportar, para respostas mais rápidas. No chat do assistente, deixe configurável.
- Use a API do Ollama com **saída estruturada** (`format` com JSON Schema). Valide o retorno com Pydantic e tente de novo uma vez se o JSON for inválido.
- Limite a entrada a cerca de 6.000 caracteres por e-mail: assunto, remetente, conta destinatária e corpo limpo, sem HTML nem assinaturas.
- Schema da análise de e-mail:

```json
{
  "categoria": "orcamento|cliente|financeiro|fornecedor|publicidade|informativo|outro",
  "importancia": "acao|importante|revisar|info",
  "motivo": "string curta",
  "resumo": "string até 240 caracteres",
  "acao_sugerida": "string ou null",
  "prazo_texto": "string ou null",
  "prazo_iso": "YYYY-MM-DD ou null",
  "trecho_prazo": "trecho literal do e-mail ou null",
  "criar_demanda": true,
  "confianca": 0.0
}
```

### Regras determinísticas

Estas regras rodam **antes e depois** da IA e prevalecem sobre ela:

- Remetente prioritário ou cliente com demanda aberta: no mínimo `importante`.
- Pedido explícito de orçamento ou prazo com data: `acao`.
- Confiança abaixo de 0,6 ou data ambígua: `revisar`.
- Publicidade: `info`, a menos que uma regra diga o contrário.
- **Na dúvida, mande para "Revisar".** Nunca esconda nem apague e-mails.

### Limites de atuação da IA

A IA **sugere**. Ela não cria demanda nem lembrete sozinha:
- O usuário aceita uma sugestão com um clique.
- Ele também pode ativar, nas configurações, a criação automática de lembretes para prazos explícitos com confiança alta.

Correções do usuário ("Importante" ou "Não é importante") são salvas e usadas como exemplos few-shot no prompt, até 10 por categoria.

### Assistente (chat)

- Use RAG simples: a pergunta passa por funções de consulta ao banco (demandas abertas, prazos, e-mails recentes, sites, arquivos, redes). O resultado vai como contexto para o modelo.
- A resposta **sempre** cita as fontes, com links para as telas internas.
- Ações que o chat pode fazer, **sempre com confirmação na interface**: criar lembrete, criar demanda, mover etapa.
- O chat **nunca** envia e-mails nem mensagens.

### Eval

Crie um script `scripts/eval_emails.py`. Ele lê um CSV de e-mails já rotulados pelo Marcos e calcula:
- recall dos importantes;
- importantes perdidos;
- alertas desnecessários;
- acerto de prazos.

A meta inicial para validar é recall de 95% ou mais nos importantes.

## 5. Integrações

| Fonte | Como | Observação |
|---|---|---|
| E-mail | IMAP com IDLE ou polling a cada 2 min | Somente leitura: `BODY.PEEK`, não marcar como lido, não mover |
| Formulários | relay → fila → `app` | Deduplicar contra o e-mail que o formulário também envia (hash de remetente + conteúdo + janela de 10 min) |
| Sites | HTTP a cada 2 min: status, tempo, texto esperado, validade do SSL | Formulário: envio de teste semanal com cabeçalho `X-Monitor-Test`, que o relay descarta |
| Uptime externo | API UptimeRobot | Fonte da verdade quando o VPS cai |
| Arquivos | Indexar a pasta local sincronizada do OneDrive (watchdog) e a "pasta de entrada" | IA sugere frente, cliente e categoria; extração de texto de PDF/DOCX; OCR opcional |
| Instagram (×4) | Instagram Graph API (contas profissionais): seguidores, posts, insights, conversas | Implementar atrás de interface `SocialProvider`, com `MockProvider` até as contas serem validadas |
| WhatsApp (×3) | WhatsApp Business **Cloud API** oficial | Mesmo esquema: interface + mock. **Não** usar bibliotecas não oficiais nem automação do WhatsApp Web |
| Avisos | Notificação do Windows + webhook do Discord (opcional) | Discord recebe só resumo e link, sem conteúdo de clientes |

## 6. Telas (seguir o protótipo)

O layout tem três partes:
- **menu lateral fixo** em azul-marinho;
- **conteúdo** fluido;
- na Visão geral, **painel do assistente** à direita.

Tudo deve ser responsivo: em telas estreitas, o menu e os painéis vão para baixo do conteúdo.

1. **Visão geral**
   - Saudação e resumo do dia, com botão "Nova demanda" (abre modal: título, frente, prazo).
   - Filtro por frente (Todas, Frente 01–04) que afeta a tela inteira.
   - 4 indicadores: demandas abertas, e-mails recebidos, sites online com alerta de formulário, mensagens pendentes.
   - "Sua fila de trabalho" com abas Hoje / Todas / Sugestões da IA. As sugestões têm os botões "Criar demanda" e "Descartar".
   - Bloco "E-mails → demandas", com o botão "+ Demanda" em cada e-mail.
   - Blocos de Sites e de Redes sociais (com mini gráfico).
   - Assistente lateral com atalhos de pergunta.
2. **Demandas**
   - Kanban com as colunas Novo → Em qualificação → Preparar proposta → Proposta enviada → Acompanhar → Ganho/Perdido.
   - Painel de detalhe com: frente, canal, contato, prazo, resumo da IA, próxima ação, histórico, link para a origem e botão "Mover para próxima etapa".
   - Drag-and-drop entre colunas.
   - Uma demanda em "Aguardando cliente" ou "Acompanhar" **exige data de retorno**.
3. **E-mails**
   - Caixa unificada com filtro por conta.
   - Abas: Todos · Importantes · Precisam de ação · Revisar · Informativos.
   - Painel de leitura com o card "Análise da mensagem": classificação, frente, prazo identificado, motivo, ação sugerida.
   - Botões: Criar demanda, Marcar importante, Não é importante.
4. **Sites**
   - Alerta destacado quando um formulário falha.
   - Indicadores: disponibilidade de 30 dias, tempo médio, incidentes, SSL mais próximo de vencer.
   - Card por site com barra de 30 dias, resposta, SSL, formulário e conteúdo.
   - Uso do VPS (CPU, RAM e disco via endpoint de métricas do relay) e lista de incidentes.
5. **Redes sociais**
   - Aviso do estado das integrações da Meta.
   - Card por perfil: seguidores, gráfico, engajamento, posts e Directs; período de 7, 30 ou 90 dias.
   - Lista "Mensagens sem resposta" com "+ Demanda".
6. **Arquivos**
   - Uso do OneDrive, busca, área de soltar arquivos na "pasta de entrada".
   - Pastas por frente e tabela com filtro por categoria.
7. **Assistente**
   - Histórico de conversas, chat em tela cheia e seletor de contexto (frente).
   - Painel "Fontes da última resposta" e lista de lembretes criados.
8. **Configurações**
   - Contas de e-mail, com formulário para adicionar e testar a conexão.
   - Status das integrações.
   - Regras de importância (interruptores e remetentes prioritários).
   - IA local: modelo, horário do resumo diário, comportamento na dúvida.

### Identidade visual

Cores sólidas, sem gradientes e sem tons pastel.

| Token | Valor |
|---|---|
| `--navy` (dominante) | `#0D213A` |
| `--navy-2` | `#1B3557` |
| `--cyan` (só detalhes) | `#00D7EC` |
| `--bg` | `#F5F7FA` |
| `--surface` | `#FFFFFF` |
| `--border` | `#D8DFE8` |
| `--subtle` | `#EEF2F7` |
| `--muted` (texto) | `#5C6B80` |
| `--danger` | `#C62828` |
| `--warning` | `#B45309` |
| `--success` | `#15803D` |

Regras de uso:
- O ciano **nunca** é usado como texto sobre branco. Ele aparece como fundo de selos ("IA"), pontos e marcadores, com texto em azul-marinho.
- Status (danger, warning, success) aparecem em texto, borda ou ponto.
- Fontes: **Bricolage Grotesque** em títulos e números, **Inter** no corpo e **IBM Plex Mono** em rótulos pequenos em caixa alta.
- Raios de 10 a 16 px e bordas finas.
- Ícones de traço (lucide-react).
- Acessibilidade:
  - contraste AA;
  - alvos de toque de 44 px ou mais;
  - navegação por teclado;
  - `aria-label` em botões só com ícone.

## 7. Segurança e privacidade

- `app` acessível apenas em localhost. O relay usa HTTPS (pelo Coolify) e tokens.
- Logs sem conteúdo de e-mail nem credenciais.
- Nenhuma ação externa sem confirmação, e nada de enviar, apagar ou mover e-mails nesta versão.
- Todo dado de cliente fica no PC e no VPS dele. Nada vai para serviços de IA na nuvem.

## 8. Qualidade

- Backend: pytest, cobrindo regras de importância, deduplicação, parser de prazos em português ("sexta", "amanhã", "até dia 15", "semana que vem"), coleta IMAP com servidor fake e fila da IA com Ollama mockado.
- Frontend: testes de componentes nas telas principais.
- Seeds com dados fictícios para desenvolver sem contas reais. A flag `MONITOR_DEMO=1` carrega os dados de demonstração.
- README com:
  - ambiente de desenvolvimento no Windows: Python, Node, Rust, Tauri CLI, Ollama e `ollama pull qwen3.5:4b-q4_K_M`;
  - como gerar o instalador;
  - deploy do relay no Coolify;
  - configuração das contas e do snippet dos formulários.

## 9. Fases de entrega

1. **Base:** monorepo, banco, migrações, design tokens, layout com menu e as 8 telas navegáveis com dados de demonstração, CRUD de demandas e kanban. **Já empacotado como programa desktop:** Tauri com o backend como sidecar, bandeja, iniciar com o Windows, instância única, tela de primeiro uso do Ollama e do modelo, e `build_windows.ps1` gerando o instalador.
2. **E-mails:** contas IMAP no keyring, coleta somente leitura, caixa unificada, fila da IA com Ollama, regras, sugestões e correções, script de eval.
3. **Lembretes e resumo diário:** lembretes, notificações do Windows, resumo da manhã às 7h30 em dias úteis.
4. **Sites e relay:** relay no VPS, formulários → demandas com deduplicação, verificações, UptimeRobot, incidentes, teste de formulário.
5. **Arquivos:** indexação da pasta do OneDrive, pasta de entrada, classificação pela IA, busca, backup do banco.
6. **Assistente:** chat com consultas ao banco, fontes citadas, ações com confirmação.
7. **Redes sociais:** providers da Instagram Graph API e da WhatsApp Cloud API atrás da interface, snapshots diários, mensagens pendentes. Discord opcional.

Ao terminar cada fase:
- rode os testes;
- atualize o README;
- liste o que ficou pendente e o que precisa do Marcos (chaves, contas, aprovação da Meta).

**Comece pela Fase 1.** Antes de escrever código, proponha a estrutura de pastas e as dependências em um parágrafo e siga.
