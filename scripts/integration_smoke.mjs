// Native IPC is stubbed; HTTP, FastAPI and SQLite are real and isolated.
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readdir } from "node:fs/promises";
import { resolve, join } from "node:path";
import { createInterface } from "node:readline";
import { once } from "node:events";
import { createServer } from "node:http";
let websiteStatus = 200;
const website = createServer((req, res) => {
  res.writeHead(websiteStatus, { "Content-Type": "text/html; charset=utf-8" });
  res.end(websiteStatus === 200 ? "Contato do teste Monitor" : "Indisponivel");
});
await new Promise((resolve) => website.listen(0, "127.0.0.1", resolve));
const websiteUrl = `http://127.0.0.1:${website.address().port}`;
await mkdir("tmp", { recursive: true });
const directory = await mkdtemp(join(resolve("tmp"), "integration-"));
const backend = spawn(
  resolve(".venv/Scripts/python.exe"),
  ["-u", "app/backend/run_backend.py"],
  {
    env: {
      ...process.env,
      LOCALAPPDATA: directory,
      MONITOR_DEMO: "0",
      MONITOR_PARENT_PIPE: "1",
    },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
let browser;
try {
  const lines = createInterface({ input: backend.stdout });
  const [line] = await once(lines, "line");
  const connection = JSON.parse(line);
  browser = await chromium.launch({ headless: true, channel: "msedge" });
  const page = await browser.newPage();
  await page.addInitScript((connection) => {
    window.isTauri = true;
    window.__TAURI_INTERNALS__ = {
      invoke: async (command) =>
        command === "connection"
          ? connection
          : command.includes("is_enabled")
            ? false
            : 1,
      transformCallback: () => 1,
      unregisterCallback: () => {},
    };
    window.__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener: () => {} };
  }, connection);
  await page.goto("http://127.0.0.1:1420");
  await page.getByText("Backend local conectado").waitFor();
  await page.getByRole("button", { name: "Nova demanda", exact: true }).click();
  await page
    .getByLabel("Título", { exact: true })
    .fill("Demanda persistida na integração");
  await page.getByRole("button", { name: "Salvar demanda" }).click();
  await page.getByText("Demanda criada.", { exact: true }).waitFor();
  await page.reload();
  await page.getByText("Backend local conectado").waitFor();
  await page
    .locator("nav")
    .getByRole("button", { name: /Demandas/ })
    .click();
  await page
    .getByText("Demanda persistida na integração", { exact: true })
    .click();
  await page
    .getByText("Demanda criada pelo usuário.", { exact: false })
    .waitFor();
  await page.getByRole("button", { name: "Fechar detalhes" }).click();
  await page
    .locator("nav")
    .getByRole("button", { name: "Sites", exact: true })
    .click();
  await page.getByLabel("Usar endereço informado").selectOption("0");
  await page.getByLabel("Nome", { exact: true }).fill("Site da integração");
  await page.getByLabel("Endereço", { exact: true }).fill(websiteUrl);
  await page
    .getByLabel("Texto esperado (opcional)")
    .fill("Contato do teste Monitor");
  await page
    .getByRole("button", { name: "Adicionar site", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Site da integração", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Verificar agora", exact: true })
    .click();
  await page.getByText(/^Resposta válida/).waitFor();
  websiteStatus = 503;
  await page
    .getByRole("button", { name: "Verificar agora", exact: true })
    .click();
  await page.getByText(/^HTTP 503/).waitFor();
  websiteStatus = 200;
  await page
    .getByRole("button", { name: "Verificar agora", exact: true })
    .click();
  await page.getByText(/^Resposta válida/).waitFor();
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  await page.getByText("Pausado", { exact: true }).waitFor();
  if (
    !(await page
      .getByRole("button", { name: "Verificar agora", exact: true })
      .isDisabled())
  )
    throw new Error("Paused sites must not run checks");
  await page.getByRole("button", { name: "Retomar", exact: true }).click();
  await page.getByRole("button", { name: "Histórico", exact: true }).click();
  await page.getByText("Últimas 100 checagens", { exact: true }).waitFor();
  await page.screenshot({ path: "tmp/ui/sites-connected.png", fullPage: true });
  await page.reload();
  await page.getByText("Backend local conectado").waitFor();
  await page
    .locator("nav")
    .getByRole("button", { name: "Sites", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Site da integração", exact: true })
    .waitFor();
  await page
    .locator("nav")
    .getByRole("button", { name: "Lembretes", exact: true })
    .click();
  await page
    .getByLabel("O que lembrar?")
    .fill("Lembrete persistido na integração");
  const earlier = new Date(Date.now() - 60000);
  await page
    .getByLabel("Data e hora", { exact: true })
    .fill(
      new Date(earlier.getTime() - earlier.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16),
    );
  await page
    .getByRole("button", { name: "Criar lembrete", exact: true })
    .click();
  await page
    .getByText("Lembrete persistido na integração", { exact: true })
    .waitFor();
  // Real production scheduler, not a manual invocation of the reminder service.
  await page.getByText(/^Você tem um lembrete/).waitFor({ timeout: 35000 });
  await page.reload();
  await page.getByText("Backend local conectado").waitFor();
  await page
    .locator("nav")
    .getByRole("button", { name: "Lembretes", exact: true })
    .click();
  await page.getByText(/^Você tem um lembrete/).waitFor();
  await page.screenshot({
    path: "tmp/ui/reminders-connected.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Concluir", exact: true }).click();
  // Pasta de arquivos: grava a estrutura e um backup consistente do banco.
  await page
    .locator("nav")
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  const cloud = join(directory, "OneDrive", "Monitor");
  await page.getByLabel("Caminho da pasta de arquivos").fill(cloud);
  await page.getByRole("button", { name: "Salvar pasta" }).click();
  await page.getByText("Pasta de arquivos salva.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Fazer backup agora" }).click();
  await page.getByText("Backup gravado na pasta de arquivos.").waitFor();
  const backups = await readdir(join(cloud, "Backups"));
  if (!backups.some((name) => /^monitor-\d{4}-\d{2}-\d{2}\.db$/.test(name)))
    throw new Error("Backup não encontrado na pasta de arquivos");
  await mkdir("tmp/ui", { recursive: true });
  await page.screenshot({
    path: "tmp/ui/settings-connected.png",
    fullPage: true,
  });
  await page
    .locator("nav")
    .getByRole("button", { name: "Visão geral", exact: true })
    .click();
  await page.getByText("Primeiros passos").waitFor();
  await page.screenshot({
    path: "tmp/ui/overview-connected.png",
    fullPage: true,
  });
  console.log(
    "Integration: real API + SQLite, demands, sites (failure/recovery/pause/history), durable reminders, production scheduler, inbox, files folder and backup OK",
  );
} finally {
  await new Promise((resolve) => website.close(resolve));
  await browser?.close();
  backend.stdin.end();
  await Promise.race([
    once(backend, "exit"),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Backend did not exit")), 5000).unref(),
    ),
  ]);
}
