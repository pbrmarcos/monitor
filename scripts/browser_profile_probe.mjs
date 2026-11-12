// Estudo técnico: perfil dedicado + execução sem janela + sessão persistente.
// Usa só um site local e um cookie sintético. Nunca abre o perfil pessoal ou o Instagram.
import { chromium } from "@playwright/test";
import { createServer } from "node:http";
import { mkdir, mkdtemp } from "node:fs/promises";
import { resolve, join } from "node:path";

await mkdir("tmp", { recursive: true });
const profile = await mkdtemp(join(resolve("tmp"), "browser-probe-"));
const server = createServer((request, response) => {
  response.setHeader("Content-Type", "text/html; charset=utf-8");
  if (request.url === "/login") {
    response.setHeader(
      "Set-Cookie",
      "monitor_probe=synthetic; HttpOnly; SameSite=Lax; Max-Age=3600; Path=/",
    );
    response.end("Synthetic session established");
  } else {
    response.end(
      request.headers.cookie?.includes("monitor_probe=synthetic")
        ? "<span data-followers>230</span>"
        : "Login required",
    );
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  const options = {
    headless: true,
    channel: process.env.MONITOR_PROBE_BROWSER || "chrome",
    timeout: 15000,
  };
  browser = await chromium.launchPersistentContext(profile, options);
  await (await browser.newPage()).goto(`${base}/login`);
  if (
    !(await browser.cookies(base)).some(
      (cookie) => cookie.name === "monitor_probe",
    )
  )
    throw new Error("Synthetic login cookie was not established");
  await browser.close();
  browser = null;
  browser = await chromium.launchPersistentContext(profile, options);
  const page = await browser.newPage();
  await page.goto(`${base}/profile`);
  const count = await page.locator("[data-followers]").innerText();
  if (count !== "230") throw new Error("Synthetic session did not persist");
  console.log(
    "Dedicated browser profile: headless launch and synthetic session survived restart. No real account accessed.",
  );
} finally {
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}
