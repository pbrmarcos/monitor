import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect, vi } from "vitest";
import App from "./App";
import { DemandModal } from "./DemandModal";
import { useState } from "react";
import { Chat, useChat } from "./pages/Other";
import * as client from "./api";
import type { Monitor } from "./store";
import { Updates } from "./pages/Personalization";
import * as core from "@tauri-apps/api/core";
import * as app from "@tauri-apps/api/app";
import * as updater from "@tauri-apps/plugin-updater";
vi.mock("@tauri-apps/api/core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tauri-apps/api/core")>()),
  isTauri: vi.fn(() => false),
}));
vi.mock("@tauri-apps/api/app", () => ({ getVersion: vi.fn() }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: vi.fn() }));
afterEach(cleanup);
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
describe("Monitor interface", () => {
  it("shows the installed desktop version and checks updates only on request", async () => {
    const desktop = vi.mocked(core.isTauri).mockReturnValue(true);
    const version = vi.mocked(app.getVersion).mockResolvedValue("1.2.3-test");
    const check = vi.mocked(updater.check).mockResolvedValue(null);
    try {
      const user = userEvent.setup();
      render(<Updates version="backend-version" />);
      expect(
        await screen.findByText("Versão instalada: 1.2.3-test"),
      ).toBeInTheDocument();
      expect(check).not.toHaveBeenCalled();
      await user.click(
        screen.getByRole("button", { name: "Verificar atualizações" }),
      );
      expect(
        await screen.findByText(/você já tem a mais recente/),
      ).toBeInTheDocument();
      expect(check).toHaveBeenCalledTimes(1);
      expect(
        screen.getByRole("button", { name: "Verificar atualizações" }),
      ).toBeEnabled();
      const candidate = { version: "1.2.4-test", downloadAndInstall: vi.fn() };
      check.mockResolvedValueOnce(candidate as unknown as updater.Update);
      await user.click(
        screen.getByRole("button", { name: "Verificar atualizações" }),
      );
      expect(
        await screen.findByRole("button", { name: "Atualizar agora" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Verificar atualizações" }),
      ).toBeEnabled();
      expect(candidate.downloadAndInstall).not.toHaveBeenCalled();
    } finally {
      desktop.mockReturnValue(false);
      version.mockReset();
      check.mockReset();
    }
  });
  it("keeps general and work chats independent and sends their modes", async () => {
    const stream = vi
      .spyOn(client, "chatStream")
      .mockImplementation(async (_messages, delta) => {
        delta("Resposta local.");
      });
    const m = {
      connected: true,
      settings: { model: "local" },
      ollama: { available: true, models: ["local"] },
      setPage: vi.fn(),
    } as unknown as Monitor;
    function Conversations() {
      const work = useChat(m, "work"),
        general = useChat(m, "general");
      const [free, setFree] = useState(false);
      return (
        <>
          <button onClick={() => setFree(false)}>Trabalho</button>
          <button onClick={() => setFree(true)}>Conversa geral</button>
          <Chat chat={free ? general : work} />
        </>
      );
    }
    try {
      const user = userEvent.setup();
      render(<Conversations />);
      await user.type(
        screen.getByLabelText("Mensagem para o assistente"),
        "Priorizar proposta",
      );
      await user.click(screen.getByRole("button", { name: "Enviar mensagem" }));
      expect(stream).toHaveBeenNthCalledWith(
        1,
        [{ role: "user", content: "Priorizar proposta" }],
        expect.any(Function),
        "work",
      );
      await user.click(screen.getByRole("button", { name: "Conversa geral" }));
      expect(screen.queryByText("Priorizar proposta")).not.toBeInTheDocument();
      await user.type(
        screen.getByLabelText("Mensagem para o assistente"),
        "Explique as estrelas",
      );
      await user.click(screen.getByRole("button", { name: "Enviar mensagem" }));
      expect(stream).toHaveBeenNthCalledWith(
        2,
        [{ role: "user", content: "Explique as estrelas" }],
        expect.any(Function),
        "general",
      );
      await user.click(screen.getByRole("button", { name: "Limpar conversa" }));
      expect(
        screen.queryByText("Explique as estrelas"),
      ).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Trabalho" }));
      expect(screen.getByText("Priorizar proposta")).toBeInTheDocument();
      expect(screen.getByText("Resposta local.")).toBeInTheDocument();
    } finally {
      stream.mockRestore();
    }
  });
  it("navigates through all screens and filters demo demands", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByText("Explorar demonstração"));
    await user.click(screen.getByRole("button", { name: "Nextlink" }));
    expect(screen.getByText("Revisar briefing do projeto")).toBeInTheDocument();
    expect(
      screen.queryByText("Preparar proposta para Ana"),
    ).not.toBeInTheDocument();
    for (const name of [
      "Demandas",
      "Lembretes",
      "E-mails",
      "Sites",
      "Redes sociais",
      "Arquivos",
      "Assistente",
      "Configurações",
    ]) {
      const buttons = screen.getAllByRole("button");
      const navButton = buttons.find(
        (b) => b.textContent?.replace(/\d+$/, "") === name,
      )!;
      await user.click(navButton);
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    }
  });
  it("creates and completes a reminder in the preview without native notifications", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByText("Explorar demonstração"));
    await user.click(screen.getByRole("button", { name: "Lembretes" }));
    await user.type(
      screen.getByLabelText("O que lembrar?"),
      "Retornar orçamento",
    );
    await user.click(screen.getByRole("button", { name: "Criar lembrete" }));
    expect(await screen.findByText("Retornar orçamento")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Concluir" }));
    expect(screen.queryByText("Retornar orçamento")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ver histórico" }));
    expect(await screen.findByText("Retornar orçamento")).toBeInTheDocument();
  });
  it("requires follow-up date and submits explicit user input", async () => {
    const user = userEvent.setup(),
      save = vi.fn();
    render(
      <DemandModal
        value={{ stage: "acompanhar" }}
        saving={false}
        onClose={() => {}}
        onSave={save}
      />,
    );
    await user.type(screen.getByLabelText("Título"), "Retornar proposta");
    expect(screen.getByLabelText(/Data de retorno/)).toBeRequired();
    await user.click(screen.getByText("Salvar demanda"));
    expect(save).not.toHaveBeenCalled();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Etapa" }),
      "novo",
    );
    await user.click(screen.getByText("Salvar demanda"));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Retornar proposta", stage: "novo" }),
    );
  });
});
