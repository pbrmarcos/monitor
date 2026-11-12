# Estudo: redes sociais com navegador em segundo plano

**Atualização 0.7.0-alpha.1:** a coleta pelos perfis do Instagram Prospect foi implementada, com rodadas de 15 minutos, Chrome sem janela e alternativa de leitura pela página. Três contas reais foram exercitadas; uma conta ocupada foi adiada. Veja o funcionamento atual em [Redes sociais](REDES-SOCIAIS.md). O texto abaixo preserva o estudo anterior à implementação.

Estudo realizado em 12/11/2026. Não foi conectada nenhuma conta real do Instagram, não foram copiadas credenciais do Chrome pessoal e nenhum coletor horário de redes foi instalado.

## Conclusão

É tecnicamente possível executar um navegador sem janela, manter uma sessão em um perfil próprio e coletar informações periodicamente enquanto o PC e o Monitor estiverem funcionando. Isso não torna confiável, por si só, a extração dos números do Instagram. A disponibilidade dos dados, os desafios de login e a estabilidade dos seletores ainda exigem um piloto com cada conta.

Reutilizar diretamente o perfil principal já aberto no Chrome não é uma boa base para esse processo: desde o Chrome 136, a depuração remota exige um diretório de perfil não padrão. A documentação do Playwright também aponta que automatizar o perfil padrão não é suportado e que duas instâncias não podem usar simultaneamente o mesmo diretório. Fontes: [Chrome](https://developer.chrome.com/blog/remote-debugging-port), [Playwright](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-persistent-context).

## Caminhos avaliados

| Caminho | Benefício | Limite e situação |
|---|---|---|
| API oficial já integrada | Campos estruturados e coleta horária sem navegador | Precisa configurar permissões/tokens e validar contas reais; o código atual foi testado com serviço simulado |
| Chrome com perfil exclusivo por conta | Login manual inicial, depois execução sem janela; não interfere nas janelas pessoais | Sessão pode expirar, páginas mudam e alguns números podem não estar disponíveis; prova local passou, Instagram real ainda não testado |
| Extensão no Chrome pessoal | Pode ler páginas autorizadas usando a sessão existente sem extrair cookies | Exige desenvolvimento e instalação de extensão, permissões restritas aos sites e Chrome em execução; abas em segundo plano continuam fazendo parte do navegador do usuário. Não implementada |
| Importação manual de exportações | Alternativa para conferência de números, sem manter login automatizado | Não acompanha a cada hora; fluxo de importação específico ainda não implementado |

A Meta descreve mecanismos de bloqueio contra coleta automatizada sem autorização. Portanto, executar sem janela ou consultar só uma vez por hora não elimina desafios de acesso e restrições da plataforma. Isso afeta a confiabilidade da alternativa; não deve ser tratado como garantia de integração. Fonte: [posicionamento técnico da Meta](https://about.fb.com/news/2021/04/how-we-combat-scraping/).

## O que foi comprovado

O script `scripts/browser_profile_probe.mjs` abriu o Chrome sem janela usando um perfil temporário próprio. Uma página HTTP local criou um cookie sintético; o navegador foi encerrado e reaberto, e a sessão continuou permitindo ler um número fictício. A prova não usa Instagram, cookies pessoais, senhas reais nem técnicas para contornar desafios de login.

Para repetir, a partir da raiz, com as dependências de desenvolvimento e Chrome instalado:

```powershell
node scripts/browser_profile_probe.mjs
```

O perfil de teste fica em `tmp/`, ignorado pelo Git, e contém apenas dados sintéticos. A execução não demonstra acesso aos Insights, mensagens ou seguidores reais.

## Proposta para um piloto posterior

1. Manter a API como caminho principal e escolher uma conta própria para validar a alternativa pelo navegador.
2. Criar um perfil exclusivo fora do OneDrive, em `%LOCALAPPDATA%\Monitor\BrowserProfiles`, sem copiar o perfil pessoal. O dono faz o login inicial numa janela visível e resolve a autenticação de dois fatores.
3. Fechar a janela de configuração e usar esse mesmo perfil em execução sem janela, com uma coleta por hora e apenas uma instância por perfil. Sessão expirada pausa a coleta e pede novo login visível, sem tentar contornar o desafio.
4. Coletar apenas os números efetivamente exibidos nas páginas autorizadas. Registrar origem, horário e ausência de cada métrica. Falha ou sessão expirada não viram zero; o cartão mantém a última coleta com indicação de dado antigo.
5. Não abrir conversas da caixa de mensagens automaticamente: essa navegação pode mudar o estado de leitura. Métricas de mensagens exigem definição e teste próprios.
6. Avaliar um período de operação antes de considerar o coletor estável. PC desligado, aplicativo encerrado e suspensão interrompem as consultas locais.

Comparar seguidores em dois horários fornece variação líquida, não a quantidade bruta de novos seguidores. Stories podem expirar entre consultas; curtidas, comentários, alcance, visitas e mensagens exigem páginas e permissões distintas. Não estimar esses números a partir de um contador de seguidores.

Recomendação: concluir a validação das contas pela API e, se ela não cobrir a necessidade, experimentar um único perfil dedicado. A extensão é a alternativa a estudar para aproveitar sessões do Chrome pessoal, em vez de abrir o mesmo diretório de perfil em outro processo.
