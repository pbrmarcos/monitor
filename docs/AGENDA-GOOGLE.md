# Demandas no Google Agenda

O Monitor grava as demandas com data na agenda principal da conta Google que você conectar. O sentido é único: o Monitor cria, atualiza e apaga os próprios eventos e não lê os seus compromissos.

## O que vai para a agenda

- Cada demanda aberta com **prazo** ou **data de retorno** vira um evento de dia inteiro.
- Na etapa Acompanhar, o evento fica na data de retorno e o título começa com “Retorno:”. Nas demais, fica no prazo.
- O evento leva o título, a frente, a etapa e a próxima ação. Contato e resumo não são enviados.
- Demanda sem data não aparece na agenda. Ao marcar Ganho ou Perdido, ou ao excluir a demanda, o evento é removido.
- A mudança chega à agenda em segundos; se o computador estiver sem internet, o Monitor tenta de novo a cada 2 minutos.
- Se você editar um evento direto no Google, a alteração é substituída na próxima vez que a demanda mudar.

## Configuração (uma única vez)

O Google exige que cada aplicativo use uma credencial própria. Você cria a sua, gratuita, na mesma conta Google em que quer ver os eventos.

1. Abra <https://console.cloud.google.com/> com a sua conta pessoal e crie um projeto (por exemplo, “Monitor”).
2. Em **APIs e serviços › Biblioteca**, procure **Google Calendar API** e clique em **Ativar**.
3. Em **APIs e serviços › Tela de permissão OAuth** (Google Auth Platform), escolha o tipo **Externo**, preencha o nome do app e o seu e-mail, e salve.
4. Na mesma área, em **Público-alvo**, clique em **Publicar app** para passar a “Em produção”. Em modo de teste o Google encerra o acesso a cada 7 dias e o Monitor pediria a conexão de novo toda semana.
5. Em **Clientes** (ou **Credenciais › Criar credenciais › ID do cliente OAuth**), escolha o tipo **App para computador** e crie.
6. Copie o **ID do cliente** e a **chave secreta do cliente**.
7. No Monitor, abra **Configurações › Google Agenda**, cole os dois valores e clique em **Conectar conta Google**.
8. O navegador abre a tela do Google. Escolha a conta, aceite o aviso “O Google não verificou este app” (Avançado › Acessar) e **marque a permissão de eventos da agenda**.
9. Volte ao Monitor: o painel mostra a conta conectada e envia as demandas existentes.

## Segurança

- A chave secreta do cliente e o token de acesso ficam no Gerenciador de Credenciais do Windows, nunca no banco, em logs ou no prompt da IA.
- A permissão pedida é `calendar.events` (criar e alterar eventos) e o endereço de e-mail da conta, usado só para mostrar qual conta está conectada.
- **Desconectar** remove o acesso deste computador e mantém na agenda os eventos já criados. Para revogar também no Google, use <https://myaccount.google.com/permissions>.

## Limites

- A conexão com uma conta Google real ainda não foi exercitada; os testes usam um Google simulado. Erros aparecem no painel em Configurações.
- Só a agenda principal é usada. Lembretes do Monitor não são enviados para a agenda.
