# Redes sociais

O Monitor usa os perfis do Chrome já configurados no **Instagram Prospect**, sem token da Meta. A cada **15 minutos**, abre cada perfil livre em modo **headless**, lê o Instagram e fecha o navegador. Nenhuma janela é exibida. O PC e o Monitor precisam estar funcionando, inclusive na bandeja; suspensão e desligamento interrompem as rodadas.

## Conectar suas contas

1. Configure as contas e faça login no Instagram pelo Prospect.
2. Feche o Chrome da conta pelo Prospect. O Monitor não encerra o Prospect nem toma um perfil ocupado.
3. No Monitor, abra **Redes sociais → Conectar pelo Chrome do Prospect**.
4. Escolha a conta e a frente. Nomes iguais sugerem a frente automaticamente.
5. Escolha se pedidos comerciais novos devem criar demandas automaticamente e clique em **Conectar perfil do Chrome**.
6. Use o botão de atualização do cartão para coletar imediatamente. As próximas rodadas são automáticas, a cada 15 minutos.

Os perfis são encontrados em `%LOCALAPPDATA%\InstagramProspect\perfis\conta-N`; nomes e usuários vêm de uma consulta somente leitura ao `dados.db` do Prospect. Não são lidos campos de senha ou chave de IA. Perfis e cookies não são copiados para o banco do Monitor, backups ou GitHub.

## Dados e cobertura

- Totais exatos de seguidores e posts, quando disponibilizados.
- Até **12 posts recentes** e seus contadores disponíveis.
- Comentários desses posts: pela resposta da sessão, até duas páginas de 50 por post; na alternativa pela página, até 100 comentários já carregados por publicação, sem expandir respostas.
- Horário da última coleta, erro e observações de cobertura.

Se a rota interna de perfil falhar, o coletor lê o cabeçalho e as publicações da própria página, confirmando a sessão da conta. Contadores abreviados sem total exato não substituem o último valor. Dados indisponíveis aparecem como “—”.

Os números da semana cobrem os **posts observados**; não garantem todos os posts ou comentários da conta. A variação de seguidores compara uma amostra diária com sete dias atrás, ou com a amostra mais antiga disponível; é variação líquida, não o total bruto de novos seguidores. Stories e Direct não são coletados por este método.

## Comentários e demandas

Comentários de terceiros aparecem em **Comentários coletados**, com autor, texto, data, publicação e classificação. Comentários da própria conta são ignorados. A lista mostra os 200 registros mais recentes.

Com a opção automática ligada, regras locais reconhecem pedidos claros, como “quero um orçamento”, “qual o valor?”, “como contratar?” e “não recebi meu pedido”. Criam uma demanda na frente da conta, canal Instagram, com comentário e link da publicação. Não há envio de resposta, curtida ou publicação. A classificação usa regras, sem depender do Qwen, e pode exigir correções.

Comentários anteriores à conexão ficam para revisão, com tolerância de cinco minutos para diferença de relógio. Comentários sem pedido claro não criam demandas automaticamente. Você pode **Criar demanda** ou **Descartar** na lista, independentemente da classificação. A origem determinística considera publicação, autor, instante e texto, evitando duplicação entre rodadas, entre os dois leitores e ao reconectar. Alterar o texto de um comentário pode gerar outro registro, especialmente quando a página não expõe seu identificador.

**Pausar coleta** interrompe as próximas consultas. Desmarcar a criação automática afeta novos comentários; não apaga demandas existentes. Remover o perfil apaga métricas e comentários locais, preservando as demandas já criadas e o perfil do Chrome.

## Perfil ocupado e falhas

Dois Chromes não usam o mesmo perfil simultaneamente. Se o Prospect estiver com a conta aberta, o Monitor adia essa conta para a próxima rodada, preservando os últimos dados. Não mata processos nem remove locks do Chrome. Não há garantia de coleta a cada 15 minutos enquanto o perfil permanecer ocupado.

Login, autenticação adicional e limite de consultas pausam as tentativas automáticas da conta. Resolva no Prospect, feche o Chrome da conta e use **Atualizar agora** no Monitor. Não há resolução automática de desafios. Falhas não viram zero nem apagam o histórico.

## Validação

A leitura sem janela foi exercitada em três contas reais autorizadas. Uma quarta estava aberta no Prospect e foi corretamente adiada. A criação de demandas foi testada com comentários sintéticos, sem inserir tarefas de teste no banco real. Os seletores podem mudar; a operação contínua por vários dias ainda precisa ser acompanhada.

A antiga conexão por token permanece numa seção alternativa recolhida para preservar instalações existentes. O fluxo principal não depende dela. O [estudo inicial](ESTUDO-REDES-NAVEGADOR.md) registra a avaliação anterior à implementação.
