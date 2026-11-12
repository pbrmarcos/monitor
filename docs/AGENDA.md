# Agenda e notificações

Use Lembretes no menu ou Criar lembrete no detalhe de uma demanda. Informe o texto e a data/hora no fuso do computador. O banco armazena o instante em UTC. Demandas concluídas encerram os lembretes ativos vinculados; excluir a demanda cancela esses lembretes, preservando o histórico.

Adiar 15 min abre o formulário com o novo horário para confirmar. Concluir e Cancelar retiram o agendamento da lista de pendentes; Ver histórico mostra os registros anteriores.

O resumo diário usa o fuso configurado na agenda (padrão America/Sao_Paulo). Não depende de Ollama: conta demandas com prazo ou retorno até hoje, lembretes e e-mails para agir. É gerado uma vez por dia útil, a partir do horário configurado. Na demonstração não há resumo automático nem entrega nativa.

O worker verifica os agendamentos a cada 10 segundos. O processo nativo consulta a fila de avisos a cada 5 segundos, inclusive com a janela minimizada. O histórico só registra o encaminhamento após o plugin aceitar o envio. Se o processo cair exatamente entre enviar e confirmar, um aviso poderá repetir após reiniciar; a fila não promete entrega exatamente uma vez. Falhas retornadas pelo plugin preservam o aviso pendente. Bloqueios ou falhas internas do Windows podem não ser reportados; a central do Monitor mantém seu próprio histórico. Marcar como lido evita novas tentativas desse aviso.

Não desative a opção Iniciar com Windows se quiser acompanhamento automático ao ligar o PC. Fechar a janela mantém a bandeja; Sair encerra o processamento. Não há funcionamento com PC desligado até a integração com o relay.

Os detalhes do lembrete ficam ocultos nos avisos por padrão. As preferências permitem mostrar detalhes, desligar avisos nativos, ajustar o resumo e ativar a criação automática de lembretes com base nos e-mails. Ao desligar os avisos, os que ainda não foram enviados ficam silenciados; o histórico no Monitor continua acessível.

Lembretes automáticos de e-mails usam 9h do prazo no fuso configurado e uma chave por mensagem. A data também precisa ser confirmada pelo leitor de prazos, além do trecho literal e da confiança informada pelo modelo. Cancelamentos não recriam o mesmo lembrete. Ajustes manuais não são sobrescritos por novas análises. Se a mensagem virar demanda, o lembrete automático passa a ficar vinculado; demandas já encerradas não geram novos lembretes automáticos.

Validação: testes com relógio controlado para fusos, dias úteis, reinícios, reagendamento, cancelamento e entrega; teste de interface; integração com API, SQLite e scheduler reais. A exibição e o clique no Windows dependem de teste manual com aplicativo instalado.
