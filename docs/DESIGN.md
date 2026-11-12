# Regras de interface

Estas regras valem para toda tela nova ou alterada. Os valores vivem como tokens em `app/frontend/src/style.css`; use o token, nunca um número ou cor solto no componente. O teste `scripts/ui_smoke.mjs` falha se algum texto visível ficar abaixo de 11 px.

## 1. Texto

Três famílias, três pesos (400, 500, 600) e oito tamanhos. Não existe tamanho intermediário.

| Token | Tamanho | Família e peso | Onde usar |
|---|---|---|---|
| `--text-display` | 30 px | Bricolage 600 | Título da página (`h1`), um por tela |
| `--text-title-lg` | 22 px | Bricolage 600 | Título de diálogo, painel lateral e e-mail aberto |
| `--text-title` | 17 px | Bricolage 600 | Título de cartão (`h2`) |
| `--text-subtitle` | 15 px | Inter 600 | Subtítulo dentro de cartão (`h3`) |
| `--text-body` | 14 px | Inter 400 | Texto corrido, campos, itens de lista, menu |
| `--text-small` | 13 px | Inter 400–600 | Botões, texto de apoio, tabelas |
| `--text-caption` | 12 px | Inter 400–500 | Selos, contadores, datas, notas de rodapé |
| `--text-label` | 11 px | IBM Plex Mono 400, caixa alta, espaçamento 0,08 em | Rótulos pequenos: sobretítulo, cabeçalho de tabela, `dt` |

- Números de indicador usam Bricolage 600 em 32 px. É a única exceção à tabela.
- 11 px só em rótulo mono em caixa alta. Texto de leitura nunca fica abaixo de 12 px.
- Altura de linha: 1,15 no título da página, 1,3 a 1,4 nos demais títulos, 1,55 no corpo.
- Texto secundário usa `--muted`. Não use opacidade para clarear texto.
- Parágrafos de leitura têm no máximo 72 caracteres por linha.
- Os tamanhos não mudam com a largura da janela; em telas largas cresce o espaço, não a letra. Abaixo de 860 px só o título da página cai para 26 px.

## 2. Cores

Cores sólidas, sem gradientes e sem tons pastel.

| Token | Valor | Uso |
|---|---|---|
| `--navy` | `#0D213A` | Texto, menu lateral, botão principal |
| `--navy-2` | `#1B3557` | Estado ativo e hover sobre o navy |
| `--cyan` | `#00D7EC` | Só detalhe: marca, selo de IA, indicador do item ativo |
| `--bg` | `#F5F7FA` | Fundo da janela |
| `--surface` | `#FFFFFF` | Cartões, campos, diálogos |
| `--border` | `#D8DFE8` | Contorno de cartões e controles |
| `--divider` | `#E7ECF2` | Linhas internas de listas e tabelas |
| `--subtle` | `#EEF2F7` | Fundo de hover, colunas do kanban, avisos neutros |
| `--muted` | `#5C6B80` | Texto secundário |
| `--danger` `--warning` `--success` | `#C62828` `#B45309` `#15803D` | Estados |

- Ciano nunca é texto sobre branco. Como fundo, leva texto `--on-cyan`.
- **Cores personalizáveis:** o usuário pode trocar `--navy` (cor principal) e `--cyan` (destaque) em Configurações. Use sempre os tokens, nunca os valores. A cor principal também é a cor do texto, por isso só é aceita com contraste de 7:1 contra o branco; `--navy-2`, `--on-cyan` e a linha do menu são derivadas em `theme.ts`. As demais cores não mudam.
- Estado aparece em texto, borda ou ponto, nunca como fundo colorido de cartão.
- Um botão principal (navy) por região da tela. Os demais são contornados ou fantasmas.
- Contraste mínimo AA: 4,5:1 para texto e 3:1 para ícones e bordas de controle.

## 3. Espaço e forma

- Espaços em múltiplos de 4: `--s1` 4, `--s2` 8, `--s3` 12, `--s4` 16, `--s5` 20, `--s6` 24, `--s8` 32, `--s10` 40.
- Entre cartões: 20 px. Dentro do cartão: 20 px nas laterais. Entre um rótulo e seu campo: 8 px. Entre campos: 16 px.
- Raios: 6 px em selos, 10 px em controles, 14 px em cartões, 16 px em diálogos.
- Bordas de 1 px. Sombra só em elementos sobrepostos (diálogo, painel lateral, aviso flutuante).
- O conteúdo ocupa toda a largura entre o menu (240 px) e o assistente (360 px). Só texto corrido tem limite: 72 caracteres por linha em parágrafos e 80 nas mensagens do chat.

## 4. Controles

- Altura de 44 px para botões, campos e itens do menu. 36 px só em controles densos dentro de barras e linhas (`.sm`, filtro de frentes), com 8 px entre alvos.
- Botão só com ícone leva `aria-label`. Ícones decorativos levam `aria-hidden`.
- Ícones de traço (lucide): 18 px em botões e menu, 16 px em controles densos, 24 px em estados vazios.
- Foco visível em todo controle: contorno de 3 px em `--focus`.
- Tudo funciona por teclado; diálogos fecham com Esc.

## 5. Padrões

- **Cabeçalho da página:** data em rótulo, título, uma frase de apoio e, à direita, a ação principal.
- **Cartão:** título à esquerda e, à direita, um selo de estado ou uma ação discreta. Sem cartão dentro de cartão.
- **Lista:** linhas de pelo menos 64 px com título em 14 px/600, apoio em 13 px e metadado mono à direita.
- **Estado vazio:** ícone do assunto, uma frase que diz o que falta e, se houver, o botão que resolve. Não use ícone de “concluído” para algo que ainda não existe.
- **Selos:** “Demonstração” para dados fictícios, “Em breve” para o que ainda não foi entregue, selo ciano apenas para o que veio da IA local. A interface não cita números de fase.
- **Confirmações** aparecem como aviso flutuante por 5 s; **erros** ficam no topo do conteúdo até serem fechados.
- **Ações destrutivas** pedem confirmação no próprio lugar, com o botão em `--danger`.
- **Frentes** aparecem sempre pelo nome que o usuário definiu em Configurações, via `frontLabel()`; nunca escreva o nome nem “Frente 01” no componente. O padrão é Rocha Comercial, Nextlink, Carteira Pronta, WebQ.
- **Cartão de perfil social:** foto redonda de 56 px (ou iniciais), usuário em título, dois totais em 32 px e, abaixo de uma linha, os números dos últimos 7 dias. Variação positiva em `--success`, negativa em `--danger`. Dado indisponível aparece como “—”, nunca como zero.
- **Arrastar:** use eventos de ponteiro, não o arrastar nativo do HTML, que a janela do aplicativo bloqueia no Windows. O cartão acompanha o cursor, a coluna de destino ganha contorno navy e Esc cancela. Toda ação de arrastar tem um caminho equivalente por botão.
- **Não mostre o que não funciona:** sem ícones ou botões decorativos sem ação.

## 6. Larguras

| Largura | Comportamento |
|---|---|
| ≥ 1321 px | Menu, conteúdo e assistente lado a lado |
| ≤ 1320 px | Assistente desce para baixo do conteúdo |
| ≤ 1100 px | Indicadores em duas colunas; cartões em uma |
| ≤ 860 px | Menu só com ícones; formulários e e-mails em uma coluna |

## 7. Texto da interface

- Português do Brasil, frases curtas, voz ativa. Botões dizem a ação: “Salvar pasta”, “Criar demanda”.
- O mesmo nome para a mesma coisa em toda a interface: “demanda”, “frente”, “pasta de arquivos”.
- Avisos dizem o que aconteceu e o que fazer. Nada de códigos ou termos internos.
