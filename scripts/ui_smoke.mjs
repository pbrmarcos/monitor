// Prévia no navegador com dados fictícios. Exige `npm run dev` ativo.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1600, height: 1050 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.goto("http://127.0.0.1:1420");
await page.getByText("Explorar demonstração").click();
await page.evaluate(() => document.fonts.ready);
await mkdir("tmp/ui", { recursive: true });
const shot = (name) =>
  page.screenshot({ path: `tmp/ui/${name}.png`, fullPage: true });
const go = (name) =>
  page.locator("nav").getByRole("button", { name, exact: true }).click();

// Nenhum texto visível abaixo de 11px (regra de docs/DESIGN.md).
const smallest = () =>
  page.evaluate(() =>
    Math.min(
      ...[...document.querySelectorAll("body *")]
        .filter((el) => el.checkVisibility() && el.textContent.trim())
        .map((el) => parseFloat(getComputedStyle(el).fontSize)),
    ),
  );

await shot("overview");
await page.getByRole("tab", { name: /Sugestões da IA/ }).click();
await page.getByRole("button", { name: "Criar demanda", exact: true }).click();
await page.getByText("Demanda criada.", { exact: true }).waitFor();
await page.getByRole("button", { name: "Nova demanda", exact: true }).click();
await page
  .getByLabel("Título", { exact: true })
  .fill("Demanda criada no teste visual");
await page.getByRole("button", { name: "Salvar demanda" }).click();
await go("Demandas");
await page.getByText("Demanda criada no teste visual", { exact: true }).click();
await shot("detail");
await page.getByRole("button", { name: "Editar demanda", exact: true }).click();
await shot("edit-dialog");
await page.getByLabel("Etapa", { exact: true }).selectOption("acompanhar");
await page.getByLabel(/Data de retorno/).fill("2026-12-15");
await page.getByRole("button", { name: "Salvar demanda" }).click();
await shot("kanban");
// Arrastar um cartão para outra coluna com o ponteiro.
const card = page.locator(".kanban-card", {
  hasText: "Preparar proposta para Ana",
});
const destination = page.getByRole("region", { name: "Proposta enviada" });
const from = await card.boundingBox();
const to = await destination.boundingBox();
await page.mouse.move(from.x + 30, from.y + 20);
await page.mouse.down();
await page.mouse.move(from.x + 60, from.y + 40, { steps: 4 });
await page.mouse.move(to.x + to.width / 2, to.y + 80, { steps: 12 });
await destination.and(page.locator(".target")).waitFor();
await shot("kanban-dragging");
await page.mouse.up();
await destination.getByText("Preparar proposta para Ana").waitFor();
if (await page.locator(".sheet, dialog[open]").count())
  throw new Error("Soltar o cartão não deve abrir os detalhes");
await go("E-mails");
await page.getByRole("tab", { name: /Revisar/ }).click();
await page.getByText("data a confirmar").waitFor();
await page.getByRole("button", { name: "Marcar importante" }).click();
await page.getByRole("tab", { name: /Todos/ }).click();
await shot("emails");
// Responder: duas sugestões, escolher uma, selecionar um trecho e melhorar.
await page.getByRole("button", { name: "Sugerir 2 respostas" }).click();
await page.getByRole("button", { name: "Usar opção 1" }).click();
const answer = page.getByLabel("Sua resposta");
// Seleção real pelo teclado: terceira linha da resposta ("Recebi sua mensagem...").
await answer.click();
await page.keyboard.press("Control+Home");
await page.keyboard.press("ArrowDown");
await page.keyboard.press("ArrowDown");
await page.keyboard.press("Home");
await page.keyboard.press("Shift+End");
await page
  .getByRole("button", { name: "Melhorar trecho selecionado" })
  .click();
await page.getByText("Trecho original:").waitFor();
await shot("email-responder");
await page.getByRole("button", { name: "Usar versão 2" }).click();
if (!(await answer.inputValue()).includes("tudo bem?"))
  throw new Error("A versão escolhida não substituiu o trecho");
for (const name of [
  "Lembretes",
  "Sites",
  "Redes sociais",
  "Arquivos",
  "Assistente",
  "Configurações",
]) {
  await go(name);
  const size = await smallest();
  if (size < 11) throw new Error(`${name}: texto de ${size}px`);
  await shot(name.toLowerCase().replace(/\W+/g, "-"));
}
await go("Redes sociais");
if ((await page.locator(".social-card").count()) !== 4)
  throw new Error("Esperados quatro cartões de perfis na demonstração");
await go("Visão geral");
await page.setViewportSize({ width: 2560, height: 1392 });
await page
  .getByRole("button", { name: "O que priorizar hoje?", exact: true })
  .click();
// Balões acompanham o texto; não herdam a altura de 100vh do painel lateral.
async function compactMessages() {
  const sizes = await page
    .locator(".chat-log .message")
    .evaluateAll((messages) =>
      messages.map((message) => {
        const text = document.createRange();
        text.selectNodeContents(message);
        const style = getComputedStyle(message);
        return {
          height: message.getBoundingClientRect().height,
          limit:
            text.getBoundingClientRect().height +
            parseFloat(style.paddingTop) +
            parseFloat(style.paddingBottom) +
            parseFloat(style.borderTopWidth) +
            parseFloat(style.borderBottomWidth) +
            12,
          position: style.position,
        };
      }),
    );
  if (
    sizes.length < 2 ||
    sizes.some((s) => s.height > s.limit || s.position !== "static")
  )
    throw new Error(`Balões do assistente esticados: ${JSON.stringify(sizes)}`);
}
await compactMessages();
await shot("assistant-compact-bubbles");
await shot("overview-wide");
// Em tela larga o conteúdo ocupa toda a área entre o menu e o assistente.
const used = await page.evaluate(() => {
  const box = (selector) =>
    document.querySelector(selector).getBoundingClientRect();
  return box(".assistant").left - box(".content").right;
});
if (used > 48) throw new Error(`Sobram ${used}px à direita do conteúdo`);
await go("Demandas");
await shot("kanban-wide");
await go("Visão geral");
await page.setViewportSize({ width: 1600, height: 1050 });
await compactMessages();
await go("Assistente");
if (await page.locator(".chat-log .message").count())
  throw new Error(
    "A conversa geral deve começar separada da conversa de demandas",
  );
await page
  .getByLabel("Mensagem para o assistente")
  .fill("Vamos conversar sobre astronomia");
await page
  .getByRole("button", { name: "Enviar mensagem", exact: true })
  .click();
await compactMessages();
await shot("assistente-conversa");
for (const name of ["Anexar arquivo ou imagem", "Falar a mensagem"]) {
  const button = page.getByRole("button", { name });
  if (!(await button.isVisible()) || !(await button.isDisabled()))
    throw new Error(`${name}: deve aparecer desativado na prévia do navegador`);
}
await page
  .getByRole("button", { name: "Nova conversa", exact: true })
  .click();
if (await page.locator(".chat-log .message").count())
  throw new Error("Nova conversa não começou vazia");
await go("Visão geral");
await page.setViewportSize({ width: 820, height: 1000 });
await compactMessages();
await shot("compact");
if (errors.length) throw new Error(errors.join("\n"));
console.log(
  "UI smoke: sugestão, criação, edição, arrastar no kanban, e-mails, agenda, navegação e três larguras OK",
);
await browser.close();
