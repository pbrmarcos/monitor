# Imagens, registros e skills do assistente

Na página Assistente há três abas: **Conversas**, **Registros e dados** e **Skills**.

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

É possível desativar qualquer skill incluída e criar até oito personalizadas, com nome, descrição, palavras-chave e até 600 caracteres de instruções. Instruções orientam a resposta; as ações disponíveis continuam limitadas às ferramentas implementadas pelo aplicativo. Dados atuais do trabalho continuam vindo do banco.

Recursos incluídos a partir da versão **0.10.0-alpha.1**. Para atualizar o aplicativo instalado, use **Configurações → Verificar atualizações**, conclua a instalação e reabra o Monitor. Também é possível usar o instalador `.exe` ou `.msi` da release correspondente no GitHub.
