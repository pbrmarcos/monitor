# Sites: configuração e leitura dos resultados

Abra **Sites**, escolha um dos endereços informados ou preencha outro, dê um nome e selecione a frente. O número `Site #…` exibido no cartão é o identificador usado pelo relay; ele é independente da frente comercial.

O cadastro começa sem medição. O primeiro resultado chega na próxima rodada automática ou pelo botão **Verificar agora**. **Pausar** suspende as checagens daquele endereço; não suspende o recebimento de seus formulários pelo relay. **Excluir** pede confirmação e remove o site, suas checagens e incidentes. Os contatos já coletados são mantidos.

## O que a checagem significa

- É uma requisição HTTP feita pelo computador, com certificado TLS verificado e até cinco redirecionamentos. O resultado final precisa ser HTTP 2xx.
- O texto esperado é opcional e pesquisado no HTML recebido, ignorando maiúsculas/minúsculas. Não há navegador executando JavaScript: escolha uma frase presente no HTML inicial, não conteúdo que só aparece após carregar uma aplicação.
- A leitura tem limites de tempo e tamanho (2 MB). Exceder o limite gera falha de checagem, não comprova que o servidor está fora do ar.
- DNS, rede local, provedor e certificado podem causar uma falha. O diagnóstico representa a observação deste computador. Não equivale a um monitor independente da sua conexão.
- A latência é a duração da requisição e leitura, incluindo redirecionamentos; a consulta separada da validade do certificado não entra nela. O certificado exibido é do destino final HTTPS. Endereços que permanecem em HTTP não têm informação de SSL.

As checagens automáticas ocorrem a cada dois minutos, com o aplicativo aberto ou na bandeja. A rodada inicial começa cerca de dez segundos após abrir. Não há coleta com o PC desligado, suspenso ou com o aplicativo encerrado. Após cinco minutos, um resultado passa a ser exibido como antigo. Pausar não apaga os resultados anteriores.

## Histórico e avisos

O percentual conta **amostras bem-sucedidas nos últimos 30 dias**, com o total de amostras e o início da coleta visíveis. Não preenche lacunas nem estima disponibilidade contínua em períodos sem coleta. Um cadastro novo pode ter uma única amostra bem-sucedida e mostrar 100%; o total e o período observado dão o contexto.

A primeira falha abre um incidente e gera aviso na central; falhas consecutivas mantêm o mesmo incidente. A primeira recuperação fecha o incidente e gera outro aviso. Certificados com menos de 14 dias de validade geram um aviso por data de vencimento. As preferências da agenda controlam os avisos nativos; a central mantém o registro local.

O histórico mostra as últimas 100 checagens e 50 incidentes. Checagens antigas são removidas após 35 dias em uma rodada ativa; incidentes não têm limpeza automática. Alterar URL ou texto esperado inicia uma nova série de amostras e encerra incidentes em aberto da regra anterior, sem emitir aviso de recuperação. Exclusão de um site não apaga avisos já registrados na central.

## Formulários e próximos componentes

Instalação do relay, tokens, IDs, integração no servidor, recuperação e limites da deduplicação estão em [relay/README.md](../relay/README.md). O painel lista até 200 contatos por vez, priorizando os pendentes; após revisar os primeiros, os próximos pendentes aparecem na atualização. Criação de demanda depende de revisão e mantém a mensagem original no registro do formulário; o resumo da demanda comporta os primeiros 6.000 caracteres.

Faltam o monitor externo independente do VPS, métricas de CPU/RAM/disco e um teste semanal que percorra o formulário real. O endpoint de teste do relay descarta envios sintéticos, mas não garante o funcionamento da página, do CAPTCHA ou do e-mail de um site.

## API local (desenvolvimento)

Todas as rotas exigem o bearer da sessão local criado pelo desktop. Não use o token do relay para chamar esta API. Os endpoints não publicam serviços na rede: o backend escuta apenas em loopback.

| Rota | Uso |
|---|---|
| `GET /sites` | Cartões com última checagem e estatísticas observadas |
| `GET /sites/suggestions` | Endereços públicos informados pelo usuário |
| `POST /sites`, `PUT /sites/{id}`, `DELETE /sites/{id}` | Cadastro e manutenção |
| `POST /sites/{id}/check` | Checagem imediata; 409 se pausado ou rodada em andamento |
| `GET /sites/{id}/history` | Checagens e incidentes recentes |
| `GET /relay`, `PUT /relay` | Configuração; a leitura só informa se existe token |
| `POST /relay/sync` | Coleta e confirmação do lote disponível |
| `GET /forms` | Contatos, priorizando pendentes |
| `POST /forms/{id}/accept`, `POST /forms/{id}/dismiss` | Revisão dos contatos |

Configuração vazia de URL do relay desconecta e remove seu token do cofre. Alterar o endereço exige informar a credencial correspondente novamente. Uma rodada em andamento é serializada com a troca de configuração.
