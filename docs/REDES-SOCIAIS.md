# Redes sociais

O Monitor lê os números dos seus perfis do Instagram pela API oficial da Meta, uma vez por hora, sem navegador e sem publicar nada. WhatsApp e mensagens diretas ainda não estão disponíveis.

## O que cada cartão mostra

- Foto, nome de usuário e frente do perfil.
- Totais: seguidores e posts.
- Últimos 7 dias: novos seguidores, posts publicados, stories, curtidas e comentários nos posts da semana.

Como os números são calculados:

- **Novos seguidores** comparam a coleta de hoje com a de 7 dias atrás. O Monitor guarda uma coleta por dia, então o número aparece a partir do segundo dia e só cobre a semana inteira depois de 7 dias; até lá o cartão diz quantos dias a comparação cobre.
- **Stories** ficam no ar por 24 horas. O Monitor conta os que viu em cada coleta; stories publicados e expirados com o computador desligado não entram na conta. Se o Instagram não liberar a consulta de stories para a conta, o cartão mostra “—” em vez de zero.
- **Curtidas e comentários** somam os posts publicados nos últimos 7 dias, entre os 50 mais recentes.

## Conectar um perfil

A conta precisa ser **profissional** (Comercial ou Criador de conteúdo). Contas pessoais não têm acesso à API.

1. Abra <https://developers.facebook.com/apps> e crie um app do tipo Empresa (gratuito).
2. No app, adicione o produto **Instagram** e abra **Configuração da API com login do Instagram**.
3. Em **Gerar tokens de acesso**, adicione a conta do Instagram. Ela recebe um convite de testador: aceite no Instagram em Configurações › Apps e sites › Convites de testador.
4. Clique em **Gerar token**, faça login na conta e copie o token.
5. No Monitor, abra **Redes sociais › Conectar Instagram**, escolha a frente, cole o token e clique em **Conectar perfil**.

Repita os passos 3 a 5 para cada perfil. Os nomes dos menus da Meta mudam com frequência; procure pelos equivalentes se não encontrar exatamente estes.

## Segurança e limites

- O token fica no Gerenciador de Credenciais do Windows, nunca no banco, em logs ou no prompt da IA.
- O token vale 60 dias. O Monitor o renova sozinho a cada 30 dias, desde que seja aberto pelo menos uma vez nesse período; se expirar, o cartão avisa e basta gerar outro.
- A foto do perfil é copiada para o banco local, porque o endereço original expira.
- **Remover** apaga o perfil e o histórico coletado neste computador. Nada muda no Instagram.
- A conexão com uma conta real ainda não foi exercitada; os testes usam um Instagram simulado.
