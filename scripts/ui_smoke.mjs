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
await go("E-mails");
await page.getByRole("tab", { name: /Revisar/ }).click();
await page.getByText("data a confirmar").waitFor();
await page.getByRole("button", { name: "Marcar importante" }).click();
await page.getByRole("tab", { name: /Todos/ }).click();
await shot("emails");
for (const name of [
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
await go("Visão geral");
await page.setViewportSize({ width: 2560, height: 1392 });
await shot("overview-wide");
await page.setViewportSize({ width: 820, height: 1000 });
await shot("compact");
if (errors.length) throw new Error(errors.join("\n"));
console.log(
  "UI smoke: sugestão, criação, edição, e-mails, oito telas e três larguras OK",
);
await browser.close();
