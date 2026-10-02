import { test, expect, request as pwRequest } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixture = path.join(project, "e2e", "fixture_server.py");
const python = path.join(project, ".venv", "Scripts", "python.exe");
const port = 18123;
const base = `http://127.0.0.1:${port}`;
const H = "E2E_HOST_ONLY";
const G = "E2E_GUEST_ONLY";
let server: ChildProcess | undefined;

async function start(dataDir: string) {
  server = spawn(python, [fixture], {
    cwd: project, windowsHide: true,
    env: { ...process.env, KARAOKE_E2E_DATA_DIR: dataDir, KARAOKE_E2E_PORT: String(port) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let diagnostics = "";
  server.stderr?.on("data", chunk => { diagnostics += String(chunk).slice(-2000); });
  server.on("error", err => { diagnostics += String(err); });
  const api = await pwRequest.newContext({ baseURL: base });
  try {
    for (let n = 0; n < 70; n++) {
      if (server.exitCode !== null) throw new Error(`Servidor de teste saiu: ${diagnostics}`);
      try {
        const r = await api.get("/", { timeout: 700 });
        if (r.status() === 200) return;
      } catch { /* aguardando */ }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    throw new Error(`Servidor de teste não iniciou: ${diagnostics}`);
  } finally { await api.dispose(); }
}

async function stop() {
  const proc = server;
  server = undefined;
  if (!proc || proc.exitCode !== null) return;
  const exit = new Promise<void>(resolve => proc.once("exit", () => resolve()));
  proc.kill();
  await Promise.race([exit, new Promise<void>((_, reject) =>
    setTimeout(() => reject(new Error("Servidor não terminou")), 5000))]);
}

async function open(page, token: string) {
  await page.addInitScript(t => sessionStorage.setItem("karaoke.token", t), token);
  await page.goto(base);
  await expect(page.getByRole("button", { name: "Cantar", exact: true })).toBeVisible();
}

test("QR, busca, upload, processamento, letra, canto e reinício isolados", async ({ browser }) => {
  test.setTimeout(120_000);
  const dataDir = await mkdtemp(path.join(tmpdir(), "karaoke-e2e-"));
  const api = await pwRequest.newContext({ baseURL: base });
  const host = await browser.newContext();
  const guest = await browser.newContext();
  try {
    await start(dataDir);
    const hp = await host.newPage();
    const gp = await guest.newPage();
    await hp.addInitScript(() => {
      (window as any).__starts = 0;
      (window as any).__stops = 0;
      const originalStart = AudioBufferSourceNode.prototype.start;
      const originalStop = AudioBufferSourceNode.prototype.stop;
      AudioBufferSourceNode.prototype.start = function (...args) {
        (window as any).__starts++;
        return originalStart.apply(this, args as any);
      };
      AudioBufferSourceNode.prototype.stop = function (...args) {
        (window as any).__stops++;
        return originalStop.apply(this, args as any);
      };
    });
    await gp.addInitScript(() => {
      (window as any).__starts = 0;
      const original = AudioBufferSourceNode.prototype.start;
      AudioBufferSourceNode.prototype.start = function (...args) {
        (window as any).__starts++;
        return original.apply(this, args as any);
      };
    });

    await open(hp, H);
    const qr = await api.get("/api/network/qr.svg", { headers: { Authorization: `Bearer ${H}` } });
    expect(qr.status()).toBe(200);
    expect(qr.headers()["content-type"]).toContain("image/svg+xml");
    await open(gp, G);
    await hp.getByRole("search").getByLabel("Nome da música ou URL do YouTube").fill("E2E Canção");
    await hp.getByRole("search").getByRole("button", { name: "Buscar", exact: true }).click();
    await hp.getByRole("button", { name: "Adicionar", exact: true }).click();
    await hp.getByLabel("Artista", { exact: true }).fill("E2E Artista");
    await hp.getByRole("button", { name: "Confirmar", exact: true }).click();
    await hp.getByLabel("Arquivo de áudio autorizado").setInputFiles({
      name: "teste.mp3", mimeType: "audio/mpeg", buffer: Buffer.from("teste"),
    });

    const headers = { Authorization: `Bearer ${H}` };
    let sid = "";
    await expect.poll(async () => {
      const r = await api.get("/api/songs", { headers });
      const songs = await r.json();
      sid = songs[0]?.id || "";
      return songs[0]?.status;
    }, { timeout: 20000 }).toBe("CONCLUIDA");
    expect(sid).toBeTruthy();
    const lrc = await api.post(`/api/songs/${sid}/lyrics/import-lrc`, {
      headers,
      multipart: { file: { name: "teste.lrc", mimeType: "text/plain", buffer: Buffer.from("[00:01.00]Linha E2E\n[00:03.00]Segunda linha\n") } },
    });
    expect(lrc.status(), await lrc.text()).toBe(200);

    await hp.getByRole("button", { name: "Cantar", exact: true }).click();
    await gp.getByRole("button", { name: "Cantar", exact: true }).click();
    await hp.getByLabel("Selecionar música").selectOption(sid);
    await hp.getByRole("button", { name: "Exibir música para todos" }).click();
    await expect(gp.locator(".karaoke-lines")).toContainText("Linha E2E");
    await hp.getByRole("button", { name: "Habilitar áudio do host" }).click();
    await expect(gp.getByRole("button", { name: "Play", exact: true })).toBeEnabled();
    await gp.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => hp.evaluate(() => (window as any).__starts)).toBeGreaterThan(0);
    expect(await gp.evaluate(() => (window as any).__starts)).toBe(0);
    await expect(gp.locator(".karaoke-active")).toContainText("Linha E2E", { timeout: 6000 });

    await stop();
    await expect.poll(() => hp.evaluate(() => (window as any).__stops), { timeout: 5000 }).toBeGreaterThan(0);
    await start(dataDir);
    await gp.reload();
    await gp.getByRole("button", { name: "Cantar", exact: true }).click();
    await expect(gp.getByRole("button", { name: "Play", exact: true })).toBeVisible();
    await expect(gp.getByRole("button", { name: "Play", exact: true })).toBeDisabled();
    expect(await gp.evaluate(() => (window as any).__starts)).toBe(0);
    const lyrics = await api.get(`/api/songs/${sid}/lyrics`, { headers: { Authorization: `Bearer ${G}` } });
    expect((await lyrics.json()).lines[0][1]).toBe("Linha E2E");
  } finally {
    await host.close();
    await guest.close();
    await api.dispose();
    await stop();
    await rm(dataDir, { recursive: true, force: true });
  }
});
