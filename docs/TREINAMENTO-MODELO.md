# Qwen 3.5 no Monitor: personalização, memória e velocidade

O modelo alvo é `qwen3.5:4b-q4_K_M`. Ele já aceita texto e imagens. Não é necessário baixar Qwen 2.5 VL para ler prints. A personalização descrita aqui não modifica os pesos e não garante respostas corretas.

## O que o aplicativo fornece

- Instruções sobre o Monitor e suas quatro frentes; dados atuais de demandas, e-mails prioritários, lembretes e sites nas conversas de trabalho. Isso é contexto consultado no banco, não um mecanismo completo de busca semântica.
- Perfil de escrita configurado em **Seu jeito de escrever**, utilizado também no chat. O perfil descreve o estilo; não treina os pesos nem copia assinaturas para toda resposta.
- Preferências explícitas salvas como regras editáveis. Mensagens e documentos não viram regras automaticamente.
- Até 24 turnos recentes, limitados pelo espaço disponível. Conversas antigas permanecem no banco, mas o modelo não recebe todo o histórico a cada pergunta.
- Anexos de texto e imagens. Uma referência explícita como “na imagem anterior” pode reenviar a última imagem dos seis turnos anteriores da mesma conversa. Para imagens mais antigas, anexe novamente.
- Ações específicas implementadas pelo aplicativo. Conhecer uma ação não dá ao modelo acesso irrestrito ao computador ou a serviços externos.

## Velocidade

O Monitor usa contexto de 16.384 tokens para chat, triagem e respostas, com `keep_alive: 30m`. Antes, alternava entre 8.192 e 16.384, o que provocou recargas nos testes. Em **Configurações → IA local**, a pré-carga pode ser desativada e o botão **Preparar modelo** permite carregar o modelo manualmente.

A preparação automática ocorre após a inicialização e a cada dez minutos. Se outro modelo ou contexto estiver carregado, ela é adiada para não substituí-lo automaticamente. A primeira carga ainda custa tempo e ocupa VRAM; preparar em segundo plano antecipa essa espera. Desativar a opção interrompe as próximas pré-cargas; não descarrega imediatamente um modelo em uso.

Medição local em 13/11/2026: RTX 3060 Laptop de 6 GB, aproximadamente 16 GB de RAM, Ollama 0.40.16. Alternar os contextos custou aproximadamente 8 segundos de carga. Com contexto único de 16.384 e modelo já carregado, o primeiro texto apareceu em 0,63 s para pergunta curta, 2,40 s com 50 demandas fictícias, 1,43 s para imagem e 0,24 s no retorno ao texto. As cargas nessas quatro chamadas ficaram entre 0,008 e 0,011 s. O modelo leu corretamente valor e data da imagem sintética. A demora relatada de 30–60 segundos não foi reproduzida; esses números não são garantia para documentos grandes, fila de tarefas ou inicialização fria. Os scripts temporários da medição usam exclusivamente dados fictícios.

## Treinamento real dos pesos

Ainda não foi executado fine-tuning. Os Modelfiles opcionais apenas definem parâmetros e instruções para uso direto no Ollama; o Monitor fornece suas próprias instruções durante as chamadas.

Para treinar o estilo, precisamos selecionar exemplos reais de pergunta, contexto e resposta desejada; remover credenciais e dados desnecessários; separar conversas inteiras entre treino e avaliação; comparar o modelo base com o adaptado em textos, imagens e ações. E-mails enviados ajudam no estilo, mas sozinhos não ensinam uma conversa de assistente. Dados comerciais atuais devem continuar no banco, pois mudam.

O guia específico do Unsloth recomenda cerca de **10 GB de VRAM para LoRA BF16 do Qwen3.5 4B** e desaconselha QLoRA de quatro bits nessa família. A placa de 6 GB serve para esta inferência quantizada, mas não atende essa receita recomendada de treino. Treinar exigirá outra GPU adequada ou uma estratégia diferente validada. Nenhum e-mail foi exportado para treinamento ou enviado a uma GPU externa nesta etapa.

Antes de usar um modelo adaptado, é necessário medir se melhora o estilo sem prejudicar leitura de imagens, precisão e comportamento das ações. Um modelo de 4B tem limites que personalização e treinamento não eliminam.

Fontes: [Qwen 3.5 no Ollama](https://ollama.com/library/qwen3.5), [pré-carga e keep_alive](https://docs.ollama.com/faq), [Modelfile](https://docs.ollama.com/modelfile), [fine-tuning do Qwen3.5](https://unsloth.ai/docs/models/qwen3.5/fine-tune).
