# Relay de formulários

Fila FastAPI + SQLite para receber contatos enquanto o PC está desligado. Não envia e-mails. Preserve o handler de e-mail dos sites como caminho independente.

## Instalação no VPS / Coolify

1. No Monitor, cadastre os quatro sites em **Sites**. Os IDs numéricos aparecem nos cartões: não são os números das frentes.
2. Gere cinco tokens independentes com `python -c "import secrets; print(secrets.token_urlsafe(32))"`: um do aplicativo e um por site. Não publique os tokens no GitHub nem no JavaScript da página.
3. Configure no Coolify: diretório de build `relay`, Dockerfile `Dockerfile`, porta interna `8000`, domínio HTTPS, volume persistente `/data` pertencente ao UID `10001`. Healthcheck HTTP em `/health`.
4. Configure as variáveis privadas `RELAY_APP_TOKEN` e `RELAY_SITE_TOKENS`. A segunda é um JSON com IDs e tokens: `{"1":"TOKEN_DO_SITE_1","2":"TOKEN_DO_SITE_2"}`. Ajuste os IDs reais; tokens precisam ter no mínimo 32 caracteres e ser todos diferentes.
5. Em **Sites → Formulários**, informe o endereço HTTPS e o token **do aplicativo**, guardado no cofre do Windows. Use **Coletar agora** para conferir.

Alternativa Docker Compose: defina as duas variáveis no ambiente privado e execute `docker compose up -d --build` dentro de `relay/`. O Compose expõe apenas `127.0.0.1:8090`; publique por um proxy HTTPS. Não habilite várias réplicas com o mesmo SQLite. O limite de 30 envios/minuto/site é por processo e reinicia junto com ele; aplique também limites no proxy público. Use um único worker.

O relay não está implantado automaticamente. Os quatro sites continuam sem alterações até que seus handlers sejam adaptados no servidor.

## Conectar os formulários

O navegador envia ao handler do próprio site. Esse handler faz as validações já existentes (incluindo proteção contra spam), mantém o e-mail original e encaminha ao relay:

```http
POST /forms/ID_DO_SITE
Authorization: Bearer TOKEN_PRIVADO_DESTE_SITE
Content-Type: application/json

{"submission_id":"UUID_ESTAVEL_DO_ENVIO","name":"Nome","email":"contato@example.com","subject":"Orçamento","message":"Mensagem do contato"}
```

O ID permanece igual nas tentativas do mesmo contato e muda no próximo envio. Repetir ID e conteúdo devolve o mesmo evento; repetir ID com outro conteúdo gera HTTP 409. O retorno 202 confirma gravação. Não aguarde o Monitor estar online.

Em `examples/`, `submission-id.js` acrescenta um identificador ao formulário existente com `data-monitor`, sem interceptar o envio nem expor segredos. `forward.php` é uma função para chamar dentro de um handler PHP validado; não é um endpoint pronto. Para WordPress/plugins, Node ou outra plataforma, adapte o hook equivalente. Não substitua o processamento atual sem testar o fluxo completo. Se o relay falhar, preserve o e-mail; a função PHP não implementa uma fila própria de reenvio.

Um POST autenticado com **`X-Monitor-Test: 1`** é validado e descartado, sem entrar na fila comercial. Isso só confirma a comunicação com o relay. Ainda não existe teste semanal pelo formulário real: ele depende da tecnologia de cada site e de um caminho de teste seguro no handler.

## Entrega e recuperação

- `GET /events?after=0`, com o token do aplicativo, retorna até 100 eventos **não confirmados**, em ordem. O aplicativo consulta a cada minuto.
- O lote inteiro é gravado no SQLite local antes de `POST /events/ack` com `{"ids":[1,2]}`. ACK perdido ou reinício gera repetição segura. Site sem mapeamento local impede a confirmação do lote: corrija os IDs e repita.
- Cada contato aparece em **Sites → Contatos dos formulários**. Criar demanda exige revisão; aceitar novamente não duplica. Pausar um site interrompe checagens HTTP, mas mantém a coleta de formulários.
- A deduplicação com e-mail exige mesma frente, endereço, mensagem completa equivalente (espaços/maiúsculas normalizados) e diferença de até 10 minutos entre recebimentos. Não usa semelhança de IA. Templates ou carimbos atrasados podem exigir revisão manual. O `submission_id` impede repetição dentro do relay; ainda não é extraído de cabeçalhos IMAP para cruzar canais.
- O banco contém dados pessoais. O volume persiste eventos confirmados e não confirmados; não há exclusão automática nesta versão. Faça backup consistente pelo SQLite e estabeleça retenção antes de produção. Não copie somente o `.db` aberto ignorando o WAL.
- Use apenas um relay por instalação local. Ao reinstalar, restaurar banco antigo ou trocar de PC, eventos confirmados não serão reenviados automaticamente: restaure também o backup local ou faça recuperação assistida no relay. Trocar a URL muda a identidade da origem; não altere aliases com eventos em trânsito.
- Um relay no mesmo VPS não monitora a queda do próprio VPS. Monitor externo independente, métricas do host e teste sintético semanal continuam pendentes.

Testes: `python -m pytest app/backend/tests/test_forms.py`, a partir da raiz, com as dependências de desenvolvimento. Usam o relay real e bancos temporários; nada é enviado aos sites reais.
