# Guia de Configuração e Treinamento do Modelo Local (Ollama + Monitor)

Este guia ensina como deixar seu modelo local perfeitamente calibrado para atender suas necessidades, falar no seu tom, compreender imagens, continuar conversas e operar integrado ao Monitor.

---

## 1. Como a Inteligência do Monitor Funciona

O Monitor utiliza uma arquitetura em 4 camadas para que o modelo entenda seu trabalho sem você precisar treinar pesos do zero:

1. **Contexto Dinâmico (RAG Local)**: A cada mensagem de trabalho, o Monitor injeta em tempo real suas **demandas abertas** ([D...]), **e-mails prioritários** ([E...]), **lembretes** ([L...]) e **status dos sites** ([S...]).
2. **Aprendizado do seu Estilo de Escrita**: O Monitor analisa seus e-mails enviados (em *Configurações → Seu jeito de escrever*) e extrai como você cumprimenta, se despede, o nível de formalidade e expressões típicas. Esse perfil agora é injetado diretamente no assistente em todas as conversas.
3. **Memória de Preferências Duradouras**: Quando você diz no chat *"A partir de agora, responda sempre em tópicos curtos"* ou *"Sempre termine com uma pergunta"*, o Monitor memoriza essa regra na aba de regras aprendidas.
4. **Comandos Diretos Operacionais**: Se você disser *"Crie um lembrete Reunião amanhã às 15h"*, o sistema executa a ação nativamente no banco antes de consultar o modelo.

---

## 2. Visão Computacional (Receber Imagens e Entender)

> [!IMPORTANT]
> Modelos puros de texto (como `qwen2.5:3b` ou `qwen3.5:4b-q4_K_M`) **não têm olhos nativos** no Ollama — se você enviar imagens a um modelo de texto puro, o Ollama rejeita com erro.
> Para que o Ollama veja e entenda **imagens, prints de WhatsApp/Instagram, comprovantes e fotos**, utilize a versão de visão oficial da família Qwen: **`qwen2.5-vl:3b`** ou **`qwen2.5-vl:7b`**.

### Como baixar o modelo com visão no Ollama:
No terminal do Windows (PowerShell ou CMD):
```powershell
ollama run qwen2.5-vl:3b
```
Depois, nas Configurações do Monitor (*Configurações → IA local*), defina o modelo como `qwen2.5-vl:3b`.

---

## 3. Criando seu Modelo Customizado no Ollama (Modelfile)

Criamos dois arquivos prontos em `scripts/` para você criar seus modelos personalizados no Ollama com 1 comando:

### Opção A: Modelo de Texto Otimizado para Negócios
```powershell
ollama create monitor-qwen -f scripts/Modelfile.monitor-qwen
```
Esse comando cria o modelo `monitor-qwen` já com:
- Parâmetros calibrados (`temperature 0.25`, `num_ctx 8192`, `top_p 0.9`);
- Persona de copiloto comercial focada no Monitor e nas 4 frentes;
- Sem respostas vagas ou robóticas.

### Opção B: Modelo Multimodal com Visão para Anexos e Imagens
```powershell
ollama create monitor-vision -f scripts/Modelfile.monitor-vision
```
Esse comando cria o modelo `monitor-vision` capaz de:
- Ler prints de conversas (WhatsApp/Instagram) e distinguir os dois lados;
- Ler recibos, tabelas e notas fiscais;
- Sugerir respostas prontas Opção 1 (curta) e Opção 2 (completa).

---

## 4. Como Ensinar o Modelo a "Falar Como Você Fala"

1. **Conecte suas contas de e-mail**:
   - Em *Configurações → Contas de e-mail*, cadastre as contas que você usa para trabalhar.
2. **Ative o perfil de estilo**:
   - Em *Configurações → Seu jeito de escrever*, clique em **Analisar estilo**. O Monitor lê seus últimos e-mails enviados e monta sua identidade verbal.
   - O assistente adotará automaticamente essa identidade em todas as conversas do dia a dia.
3. **Use regras explícitas no chat**:
   - Na conversa com o assistente, peça preferências como:
     - *"Prefira respostas diretas e em tópicos."*
     - *"Quando for proposta comercial, use sempre um tom cordial mas sem formalidade excessiva."*
   - O Monitor salva essas memórias na barra lateral do Assistente (você pode editar ou apagar quando quiser).

---

## 5. Dicas de Produtividade no Chat

- **Priorização do dia**: *"O que tenho de mais urgente para hoje?"*
- **Acompanhamento de cliente**: *"Qual o status da proposta da Ana na Rocha Comercial?"*
- **Ação direta**: *"Crie um lembrete Retornar para Pedro amanhã às 10h"*
- **Análise de imagem**: Arraste um print de conversa para o chat e clique em *"Sugerir próximas mensagens"*.
