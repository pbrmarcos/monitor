# Conversas e aprendizado do assistente

A **Visão geral** mantém o assistente de trabalho, com demandas, prazos, e-mails, lembretes e sites. A tela **Assistente** tem uma lista de conversas e permite abrir uma conversa geral ou uma conversa sobre o trabalho. As citações de demandas, como `[D12]`, abrem o registro quando ele ainda existe no Monitor.

## Conversas salvas

- **Nova conversa** começa uma conversa geral; **Sobre meu trabalho** começa uma conversa com contexto comercial.
- O título é formado pela primeira pergunta. A conversa passa a aparecer na lista após o primeiro envio.
- Perguntas e respostas ficam no SQLite deste computador e acompanham os backups. Elas podem ser reabertas depois de reiniciar o aplicativo.
- A lixeira pede confirmação antes de excluir a conversa e suas mensagens. Uma resposta em andamento não recria uma conversa já excluída.
- Falhas detectadas no fluxo de resposta ficam identificadas como erro. O modelo considera as mensagens recentes, não todo o arquivo de conversas anteriores. A lista mostra as 200 conversas recentes.

## Preferências aprendidas

Você pode dar uma instrução duradoura, por exemplo: **“A partir de agora, sempre me chame de Marcos e responda em no máximo duas frases.”** O aplicativo registra esse pedido como uma preferência visível em **Regras aprendidas**. Também é possível adicionar uma preferência manualmente.

O registro automático é deliberadamente verificável: guarda uma instrução explícita sua, com até 200 caracteres, ligada ao comportamento das respostas. Perguntas comuns, instruções citadas e comandos produzidos pelo modelo não são transformados em memórias. Textos dos e-mails e dos registros comerciais não têm autorização para criar regras. São aceitas algumas formas diretas de pedido, como “Responda sempre…”, “A partir de agora…” e “Prefiro respostas…”. Pedidos ambíguos ou muito longos devem ser resumidos e adicionados pelo campo manual.

As preferências ficam visíveis e podem ser apagadas. Valem para as conversas seguintes, inclusive entre os modos geral e trabalho; não são treinamento dos pesos do modelo nem alteração das regras de e-mail, das demandas ou das permissões do aplicativo. A conversa geral recebe essas preferências explícitas, mas não coleta automaticamente os registros comerciais.

Apagar uma conversa mantém as preferências aprendidas. Para esquecê-las, apague também as respectivas regras. Os turnos em que uma preferência foi guardada ficam no histórico visível, mas não são reenviados como instruções: a lista ativa de regras determina as preferências aplicadas. Assim, uma regra apagada não é recriada a partir de respostas antigas. Esse comportamento é explicado junto à lista de regras e no pedido de exclusão. O limite é de 50 preferências; repetições textuais, ignorando maiúsculas e pontuação final, não criam cópias.

O modelo pode aplicar uma preferência de forma imperfeita; revise as respostas. Na validação com o Qwen local, uma pergunta comum não criou memória, o pedido explícito foi salvo uma única vez e a resposta seguinte respeitou o limite de duas frases. Isso é um teste pontual, não uma medição de precisão.

## Dados e limites

Conversas e preferências são locais. Excluir no banco em uso não apaga cópias já existentes nos seus backups; elas seguem a retenção configurada. Senhas e tokens não entram no contexto preparado pelo Monitor. O assistente usa o modelo do Ollama configurado no aplicativo, sem navegação na internet e sem executar operações comerciais.
