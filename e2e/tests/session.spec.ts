import { test, expect, type Page } from "@playwright/test";

const hostToken = process.env.KARAOKE_E2E_HOST_TOKEN;
const guestToken = process.env.KARAOKE_E2E_GUEST_TOKEN;

async function enter(page: Page, token: string, badge: string) {
  await page.addInitScript(value => sessionStorage.setItem("karaoke.token", value), token);
  await page.goto("/");
  await expect(page.getByText(badge, { exact: true })).toBeVisible();
}

test("host e convidado acessam a mesma sessão sem áudio no convidado", async ({ browser, request }) => {
  if (!hostToken || !guestToken) {
    throw new Error("Defina KARAOKE_E2E_HOST_TOKEN e KARAOKE_E2E_GUEST_TOKEN antes do teste.");
  }
  for (const [role, token] of [["host", hostToken], ["guest", guestToken]] as const) {
    const response = await request.post("/api/session/join", { data: { token } });
    if (!response.ok()) {
      throw new Error(`Token de ${role} rejeitado pela API (${response.status()}). Verifique as variáveis do Playwright e os tokens da API ativa; não envie os tokens aqui.`);
    }
    const identity = await response.json();
    expect(identity.role, `O token de ${role} pertence a outro papel`).toBe(role);
  }

  const host = await browser.newContext();
  const guest = await browser.newContext();
  try {
    const hp = await host.newPage();
    const gp = await guest.newPage();
    await enter(hp, hostToken, "Host (pode enviar e excluir arquivos)");
    await enter(gp, guestToken, "Convidado");

    await hp.getByRole("button", { name: "Cantar", exact: true }).click();
    await gp.getByRole("button", { name: "Cantar", exact: true }).click();
    await expect(hp.getByRole("heading", { name: "Sessão de karaokê" })).toBeVisible();
    await expect(gp.getByRole("heading", { name: "Sessão de karaokê" })).toBeVisible();
    await expect(gp.getByText("Este dispositivo não reproduz áudio. Apenas o host emite som.")).toBeVisible();
  } finally {
    await host.close();
    await guest.close();
  }
});
