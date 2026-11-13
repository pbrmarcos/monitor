# Conversas e aprendizado do assistente

A **Visão geral** mantém o assistente de trabalho, com demandas, prazos, e-mails, lembretes e sites. A tela **Assistente** tem uma lista de conversas e permite abrir uma conversa geral ou uma conversa sobre o trabalho. As citações de demandas, como `[D12]`, abrem o registro quando ele ainda existe no Monitor.

## Ações pelo chat

Pedidos diretos agora executam operações reais, tanto no assistente de trabalho quanto na conversa geral. O resultado é produzido pelo executor e pelo banco, não por uma promessa do modelo. O selo **Resultado registrado** e o botão para abrir o registro acompanham a confirmação e permanecem no histórico após reiniciar.

Exemplos:

- **Crie um lembrete Consulta de exemplo 08/12/2026 às 14:30.**
- **Me lembre de ligar para o cliente daqui a 20 minutos.**
- **Reagende o lembrete [L3] para amanhã às 10h.**
- **Conclua o lembrete [L3].** ou **Cancele o lembrete [L3].**
- **Crie uma demanda Preparar proposta para Nextlink até 20/11/2026.**
- **Mova a demanda [D2] para Proposta enviada.**
- **Altere a demanda [D2] para prioridade alta.**

A interpretação dessas operações é determinística e funciona sem o Ollama. Consultas e conversa livre continuam usando o modelo local. O usuário precisa pedir a ação diretamente: texto de e-mail, preferência aprendida ou saída do modelo não executa ferramenta. Formas comuns como “quero criar”, “você pode criar” e “adiciona um lembrete” são aceitas. Não há execução arbitrária de comandos do computador.

Se faltar título, data, horário, identificador ou frente, o chat pede o dado necessário e mantém um pedido pendente por até 24 horas, separado por conversa. Responda com o dado que falta ou diga **cancele**. Uma nova instrução direta substitui o pedido pendente. A frente selecionada nas abas pode ser usada quando o pedido de demanda não cita outra frente; com Todas as frentes, o chat pergunta qual usar.

Lembretes usam o fuso configurado em **Configurações → Agenda** e não são criados no passado. Datas brasileiras, datas ISO, hoje, amanhã, dias da semana e intervalos como “daqui a 20 minutos” são reconhecidos. Envie uma ação por mensagem. Para modificar um registro, use seu identificador, como `[L3]` ou `[D2]`; o assistente não escolhe um registro por semelhança de nome.

Repetir a criação de um lembrete pendente com o mesmo texto e horário reutiliza o registro; a mesma demanda aberta, com frente e prazo iguais, também não ganha outra cópia. Demandas e lembretes têm identificadores que não são reutilizados após exclusão, preservando as referências do histórico. Excluir uma conversa mantém os registros já criados: cancelar um lembrete ou alterar uma demanda é outra ação explícita.

### Google Agenda

Acrescente **no Google** ou **na minha agenda do Google** ao pedido de lembrete para solicitar um evento com horário na agenda principal conectada. Exemplo: **Crie um lembrete Consulta amanhã às 14:30 no Google por 1 hora.** Sem duração informada, o evento dura 30 minutos, indicados na resposta.

O lembrete é salvo primeiro no Monitor. Com a conta conectada, o aplicativo tenta enviar o evento e só informa sincronização quando o estado confirmado corresponde ao pedido atual. Sem conexão ou em uma falha, confirma o registro local e informa o envio pendente. Conecte a conta em Configurações; o scheduler tenta a sincronização a cada dois minutos. Identificadores de evento persistidos evitam duplicação ao repetir envios.

Só os lembretes cujo envio foi pedido entram na agenda; criar um lembrete local não envia seu título ao Google. Reagendar um lembrete vinculado atualiza o evento. Cancelar remove o evento; concluir o lembrete mantém o compromisso na agenda. Não são adicionados convidados nem enviados convites. A conexão OAuth continua sendo necessária uma vez; veja [Google Agenda](AGENDA-GOOGLE.md).

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

Conversas, preferências e registros de ações são locais. Excluir no banco em uso não apaga cópias existentes nos backups; elas seguem a retenção configurada. O contexto automático não lê senhas e tokens do cofre. As ferramentas são limitadas às operações descritas acima; não enviam e-mails nem mensagens sociais. O envio ao Google ocorre quando solicitado e usa a conta conectada. A conversa geral continua sem consulta comercial automática, mas pode consultar os resultados confirmados das próprias ações no seu histórico.
