// Native IPC is stubbed; HTTP, FastAPI and SQLite are real and isolated.
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readdir } from "node:fs/promises";
import { resolve, join } from "node:path";
import { createInterface } from "node:readline";
import { once } from "node:events";
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
    "Integration: real API + SQLite, create, reload persistence, audit history, files folder and backup OK",
  );
} finally {
  await browser?.close();
  backend.stdin.end();
  await Promise.race([
    once(backend, "exit"),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Backend did not exit")), 5000).unref(),
    ),
  ]);
}
