# Aprender o seu jeito de escrever e responder e-mails

O Monitor só redige: **nenhuma mensagem é enviada** e nada é gravado no servidor de e-mail. Os textos passam apenas pelo modelo local.

## Como ele aprende

- Na primeira coleta de cada conta, o Monitor traz os **100 e-mails mais recentes** da caixa de entrada e, em modo somente leitura, os da pasta de enviados. A pasta de enviados é reconhecida pela marcação do servidor ou por nomes comuns (Sent, Enviados, Itens Enviados, Gmail). Se não encontrar, a conta fica com um tom neutro e o painel avisa.
- A cada 30 minutos, ou ao clicar em **Reaprender**, os enviados novos são lidos e o perfil é atualizado quando há pelo menos 10 mensagens novas.
- O perfil junta o que é contado sem IA (saudação e despedida mais usadas, tamanho médio) e uma descrição escrita pelo modelo (tom, expressões, tratamento). Ele aparece em **Configurações › Seu jeito de escrever** e pode ser editado; um perfil editado por você não é sobrescrito pela rotina automática.
- Quem recebeu e-mail seu passa a ser tratado como importante: “Você já escreveu para este remetente” entra no motivo da análise.

## Responder

Em **E-mails**, abra a mensagem e use o bloco **Responder**:

1. Escreva, se quiser, o que pretende dizer (“aceitar e dizer que entrego na sexta”).
2. **Sugerir 2 respostas** gera uma direta e uma completa no seu estilo. Respostas anteriores ao mesmo destinatário servem de exemplo. Use uma das opções ou escreva a sua.
3. Selecione uma frase ou um parágrafo e clique em **Melhorar trecho selecionado**: aparecem duas versões só daquele trecho (direta e cordial), e você escolhe qual substitui o original ou mantém o original.
4. O rascunho é salvo sozinho. **Copiar resposta** leva o texto para enviar pelo seu programa de e-mail.

O que o modelo não sabe vira **[colchetes]** para você preencher. Ele pode errar ou prometer o que você não combinou, por isso o bloco sempre mostra o aviso de revisão.

## Privacidade

- Os enviados lidos ficam só no banco local (`%LOCALAPPDATA%\Monitor`) e só os de poucas mensagens entram no pedido ao modelo.
- Remover uma conta apaga também os enviados, o perfil e os rascunhos dela.
- Senhas continuam no Gerenciador de Credenciais do Windows e nunca vão ao modelo.

## Não validado

Contas IMAP reais (inclusive o nome real da pasta de enviados de cada provedor), a qualidade do perfil com e-mails seus e o desempenho com caixas grandes. Os testes usam um servidor IMAP simulado e o modelo local com e-mails fictícios.
