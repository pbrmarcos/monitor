# Anexos, prints de conversa e microfone no assistente

Tudo acontece neste computador. Os arquivos e a voz passam apenas pelo modelo local (Ollama e Whisper) e nada é enviado a serviços na nuvem.

## Anexar arquivos e imagens

Na caixa de mensagem do assistente, use o clipe, arraste um arquivo para a caixa ou cole um print (Win+Shift+S e depois Ctrl+V).

| Tipo | Como é lido |
|---|---|
| Texto: `.txt` `.md` `.csv` `.tsv` `.json` `.log` `.eml` `.xml` `.html` | Texto direto; HTML vira texto simples |
| PDF | Texto selecionável das primeiras 80 páginas. PDF digitalizado (só imagem) é recusado: envie as páginas como imagem |
| Word `.docx` | Parágrafos e tabelas |
| Excel `.xlsx` | Células de todas as abas, até 2.000 linhas por aba |
| Imagem PNG ou JPEG | O modelo de visão lê a imagem. Capturas grandes são reduzidas a 1.568 px e viram JPEG antes de seguir |

Limites: 10 MB por arquivo, 5 anexos e 2 imagens por mensagem, 40 mil caracteres de texto por arquivo. Arquivos `.doc`, `.xls`, `.pptx`, executáveis e compactados são recusados com uma mensagem.

Como o assistente trata os anexos:

- O texto do arquivo acompanha a conversa: você pode fazer perguntas seguintes sobre ele. A imagem só é enviada na mensagem em que foi anexada; nas seguintes o assistente usa a leitura que ele mesmo fez.
- O conteúdo é tratado como dado, nunca como instrução. Um documento que mande "ignorar as regras" ou "criar um lembrete" não faz nada, e preferências do assistente só nascem do que você digita.
- Anexos não enviados somem em 1 dia; ao excluir a conversa, os anexos dela são apagados.

## Sugerir as próximas mensagens a partir de um print

1. Cole ou anexe o print da conversa (WhatsApp, Instagram, e-mail).
2. Se quiser, escreva uma orientação: “posso baixar até R$ 3.800”.
3. Clique em **Sugerir próximas mensagens**.

O assistente responde com **Situação** (em que ponto a conversa está), **Opção 1** (curta e direta) e **Opção 2** (mais completa). Ele imita o seu jeito de escrever usando o perfil aprendido nos seus e-mails enviados ([RESPOSTAS.md](RESPOSTAS.md)) e deixa **[colchetes]** no que só você sabe. Você copia, ajusta e envia pelo próprio aplicativo; o Monitor não envia nada.

Limites: o modelo local é pequeno e pode errar, ler mal um trecho pequeno ou inventar um prazo, então revise antes de enviar. A primeira leitura de imagem após abrir o Ollama leva cerca de 50 segundos (carrega a parte de visão); depois, poucos segundos.

## Microfone

O botão de microfone grava a sua voz e coloca o texto na caixa de mensagem. Ele **não envia sozinho**: você revisa e envia.

Configuração, uma vez: **Configurações › Voz e microfone** › escolha a qualidade e **Baixar modelo**.

| Qualidade | Download | Quando usar |
|---|---|---|
| Rápido | 75 MB | Computador lento ou frases curtas |
| Equilibrado | 145 MB | Uso geral |
| Preciso (padrão) | 484 MB | Melhor para português e nomes próprios |

- O modelo vem do repositório público `Systran/faster-whisper-*` no Hugging Face e o arquivo principal tem o SHA-256 conferido. Se a conexão cair, o download continua de onde parou.
- A transcrição roda no processador, sem enviar áudio a ninguém, e o áudio não é guardado. O modelo sai da memória após 10 minutos sem uso.
- Cada gravação vai até 3 minutos. Esc cancela. Os nomes das suas frentes e “Monitor” ajudam o reconhecimento.
- Na primeira gravação o Windows pode pedir permissão para o microfone. Se negar sem querer: Configurações do Windows › Privacidade e segurança › Microfone.

O motor de voz aumenta o instalador em cerca de 115 MB (bibliotecas Whisper e de áudio).

## O que ainda não foi validado

- A transcrição com um modelo real e fala real: os testes usam um motor simulado, e o executável empacotado foi verificado até o carregamento das bibliotecas com um modelo falso.
- A permissão do microfone e a gravação dentro da janela do aplicativo instalado (WebView2).
- Arrastar um arquivo do Explorer para dentro da janela instalada. A janela foi configurada para isso, mas não foi testada instalada.
- O build do instalador no GitHub Actions com as novas dependências.
