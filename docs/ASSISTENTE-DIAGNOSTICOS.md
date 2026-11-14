# Imagens, registros e skills do assistente

Na página Assistente há três abas: **Conversas**, **Registros e dados** e **Skills**.

## Sequências e versões de mensagens (0.11.0-alpha.1)

Pedidos como “escreva 4 mensagens próximas” geram uma sequência de quatro passos; “4 mensagens diferentes com abordagens diferentes” ou “uma mensagem em 4 tons” geram alternativas para escolher uma. A interpretação automática cobre quantidades de 2 a 8, inclusive números por extenso e “mensagems”. Fora desse fluxo, o pedido continua na conversa comum.

Cada versão tem um botão de copiar. Nas alternativas, as abas mostram um tom de cada vez. A sequência mantém todas as mensagens visíveis. O usuário ainda revisa e envia as mensagens; não há envio automático. As abas permanecem ao reabrir uma conversa e somem com sua exclusão.

Para imagens, o mesmo Qwen primeiro transcreve e separa participantes, fatos e pendências. Na redação, a transcrição inteira e respostas anteriores que podem estar erradas não disputam o lugar do resumo atual. O contexto da imagem e do modelo é guardado na própria conversa, sem compartilhamento entre conversas. A imagem mais recente entre os turnos considerados pode ser retomada automaticamente numa correção que pede novas mensagens.

Quando a fonte identifica um orçamento com especificações a confirmar e um item recebido cuja manutenção ou devolução depende do cliente, o Monitor oferece quatro rascunhos guiados com esses campos. Esse fluxo não delega novamente ao modelo a história do pedido nem inventa prazo de fábrica. Nos outros casos, a redação usa chamadas curtas por item, com uma tentativa de reparo para formato, repetições e algumas inconsistências de referências, números e prazos. Essas checagens não demonstram precisão semântica geral.

Métricas somam o trabalho das chamadas feitas para atender o pedido, incluindo leitura da imagem e tentativas descartadas. O contexto lido pode ser reutilizado sem inferência nova; nesses casos o painel informa zero chamadas, sem fabricar uma velocidade de geração. O raciocínio interno do modelo não é armazenado nem mostrado.

## Imagens

Clique no anexo de imagem de uma mensagem para abrir o visualizador. Ele oferece zoom de 50% a 300%, ajuste à tela e fechamento por Esc. Funciona também ao reabrir uma conversa salva e no assistente lateral da visão geral. Mostra a imagem que o Monitor armazenou; capturas grandes podem ter sido reduzidas antes do envio. A consulta exige a mesma autenticação local das conversas e não usa URLs com tokens. Excluir a conversa exclui seus anexos.

## Métricas e registros

Respostas novas mostram os tokens gerados, tk/s e duração quando o Ollama fornece as métricas. Abra o detalhe para consultar tokens de entrada, tempo de leitura do contexto, carga do modelo, geração e tempo até o primeiro texto. **tk/s = eval_count / (eval_duration / 1e9)**; essa velocidade não inclui a carga nem a leitura do contexto. Não são métricas de qualidade da resposta. Modelos sem métricas, respostas antigas e ferramentas locais não ganham números inventados.

As métricas ficam associadas à resposta no SQLite e continuam disponíveis ao reabrir a conversa. Limpar os logs técnicos não apaga essas métricas, nem as conversas. Excluir uma conversa apaga também suas métricas.

Os registros técnicos mostram execuções do chat, processamento por ferramentas locais e recebimento de anexos. Não são um log de todos os serviços do Monitor ou uma exposição do raciocínio interno do modelo. Guardam estado, modelo, horários, métricas e nomes das skills; não duplicam perguntas, respostas, credenciais ou imagens. A retenção preserva os 200 registros recentes e execuções em andamento. Na reinicialização, execuções que ficaram em andamento são marcadas como interrompidas.

A tela de dados consulta o Ollama ao abrir e ao clicar em Atualizar. Mostra o modelo selecionado, contexto, permanência em memória e bytes alocados pelo modelo na GPU conforme `/api/ps`. Esse valor não representa toda a VRAM ocupada pelo Windows e outros programas. Nenhum monitoramento adicional da GPU roda em segundo plano.

## Skills e GPU de 6 GB

O modelo continua sendo o selecionado em Configurações, inclusive `qwen3.5:4b-q4_K_M`. As skills não baixam outro modelo, não treinam pesos e não executam código. São instruções curtas sobre leitura cuidadosa de imagens, próximo passo comercial, prazos e escrita no tom do usuário.

Cada pergunta recebe no máximo duas skills, escolhidas por palavras-chave e presença de imagem. Isso acrescenta texto ao prompt e pode aumentar um pouco a leitura do contexto, mas mantém a configuração de 16.384 tokens. Não há promessa de consumo total fixo de VRAM: outros programas, imagens e o modelo escolhido também influenciam.

É possível desativar qualquer skill incluída e criar até oito personalizadas, com nome, descrição, palavras-chave e até 4.000 caracteres de instruções ativas. Instruções orientam a resposta; as ações disponíveis continuam limitadas às ferramentas implementadas pelo aplicativo. Dados atuais do trabalho continuam vindo do banco.

### Importar arquivos Markdown (0.10.1-alpha.1)

Em **Assistente → Skills → Importar skill .md**, escolha um arquivo `.md`, `.markdown` ou `.txt` em UTF-8, de até 128 KB e 100 mil caracteres. Revise nome, descrição, palavras-chave e instruções ativas antes de salvar. Importar preenche um rascunho; não ativa automaticamente o conteúdo.

O documento completo fica guardado no SQLite para consulta. Somente as instruções ativas são enviadas ao modelo. Campos textuais simples `name`, `description` e `keywords` no cabeçalho `---` são reconhecidos; não há execução de YAML, scripts, comandos, links, ferramentas ou arquivos referenciados. Isso não instala plugins de Codex, Claude ou outros agentes.

Arquivos curtos podem fornecer diretamente as instruções. Em arquivos longos, use uma seção **`## Instruções ativas`** de até 4.000 caracteres e coloque o restante em outra seção, como **`## Referência`**. Sem essa seção, se o corpo exceder o limite, o Monitor preserva o original e pede uma adaptação revisada; não trunca nem resume o documento automaticamente. O texto da referência não participa de busca ou recuperação automática nesta versão.

Skills personalizadas podem ser editadas, preservando a referência. As skills da versão anterior continuam funcionando após a migração.

Ao criar uma versão personalizada de uma skill incluída, desative a incluída se ambas tratarem da mesma tarefa. Isso evita gastar contexto com orientações repetidas ou contraditórias.

A skill incluída **Remover padrões de escrita de IA** é uma [adaptação curta](../app/backend/monitor/skills/remover-padroes-ia.md) para revisões e reescritas, com prioridade nesse tipo de pedido. Ela não orienta todas as conversas. O original fornecido pelo usuário tinha 34.334 caracteres; o aplicativo distribui a adaptação, não esse documento inteiro.

Nos dois textos fictícios testados no Qwen3.5 4B Q4_K_M, a versão adaptada usou entradas de aproximadamente 770 tokens e preservou os dados. O documento completo usou cerca de 8.440 tokens; em um dos casos, o modelo misturou a condição de pagamento com a entrega e manteve expressões genéricas. A adaptação também manteve um termo genérico em uma saída. Isso demonstra a necessidade de revisar o resultado; não mede uma taxa geral de acerto nem garante o cumprimento de todas as regras. O contexto permaneceu em 16.384 tokens e a alocação do modelo reportada pelo Ollama foi de aproximadamente 3,31 GiB de VRAM, excluindo o uso dos outros programas.

Recursos incluídos a partir da versão **0.10.0-alpha.1**. Para atualizar o aplicativo instalado, use **Configurações → Verificar atualizações**, conclua a instalação e reabra o Monitor. Também é possível usar o instalador `.exe` ou `.msi` da release correspondente no GitHub.
