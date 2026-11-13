import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ReplyBox } from "./pages/Reply";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect, vi } from "vitest";
import App from "./App";
import { DemandModal } from "./DemandModal";
import { AssistantPage, useAssistant } from "./pages/Assistant";
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
  it("shows a recorded assistant action and opens the reminders screen", async () => {
    const calls = vi
      .spyOn(client, "api")
      .mockImplementation(async (path, method) =>
        path === "/assistant/conversations" && method === "POST"
          ? ({
              id: 1,
              mode: "general",
              title: "",
              updated_at: new Date().toISOString(),
            } as never)
          : ([] as never),
      );
    const stream = vi
      .spyOn(client, "conversationStream")
      .mockImplementation(async (id, content, on) => {
        on.delta("Criado [L5]: Consulta. Data: 08/12/2026 às 14:30.");
        on.action?.({
          kind: "reminder",
          id: 5,
          operation: "created",
          text: "Consulta",
        });
        on.done({
          id,
          mode: "general",
          title: content,
          updated_at: new Date().toISOString(),
        });
      });
    const m = {
      connected: true,
      front: 4,
      settings: { model: "local" },
      ollama: { available: false, models: [] },
      demands: [],
      refreshDemands: vi.fn(async () => {}),
      setPage: vi.fn(),
      setNotice: vi.fn(),
      setDetail: vi.fn(),
      fail: vi.fn(),
    } as unknown as Monitor;
    function Page() {
      return <AssistantPage a={useAssistant(m)} />;
    }
    try {
      const user = userEvent.setup();
      render(<Page />);
      await user.type(
        screen.getByLabelText("Mensagem para o assistente"),
        "Crie um lembrete Consulta amanhã às 9h",
      );
      await user.click(screen.getByRole("button", { name: "Enviar mensagem" }));
      expect(
        await screen.findByText("Resultado registrado"),
      ).toBeInTheDocument();
      expect(m.refreshDemands).toHaveBeenCalled();
      expect(stream).toHaveBeenCalledWith(
        1,
        "Crie um lembrete Consulta amanhã às 9h",
        expect.objectContaining({ front_id: 4 }),
      );
      await user.click(screen.getByRole("button", { name: "Abrir lembretes" }));
      expect(m.setPage).toHaveBeenCalledWith("Lembretes");
    } finally {
      stream.mockRestore();
      calls.mockRestore();
    }
  });
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
  it("saves separate conversations, learns a rule and deletes a conversation", async () => {
    let next = 1;
    const calls = vi
      .spyOn(client, "api")
      .mockImplementation(
        async (path: string, method = "GET", body?: unknown) => {
          if (path === "/assistant/conversations" && method === "POST")
            return {
              id: next++,
              mode: (body as { mode: string }).mode,
              title: "",
              updated_at: new Date().toISOString(),
            } as never;
          if (method === "GET") return [] as never;
          return undefined as never;
        },
      );
    const stream = vi
      .spyOn(client, "conversationStream")
      .mockImplementation(async (id, content, on) => {
        on.delta("Resposta local.");
        if (content.includes("sempre"))
          on.rule({
            id: 9,
            text: "Responder em tópicos",
            source: "assistente",
          });
        on.done({
          id,
          mode: id === 1 ? "general" : "work",
          title: content,
          updated_at: new Date().toISOString(),
        });
      });
    const m = {
      connected: true,
      settings: { model: "local" },
      ollama: { available: true, models: ["local"] },
      demands: [],
      setPage: vi.fn(),
      setNotice: vi.fn(),
      setDetail: vi.fn(),
      fail: vi.fn(),
    } as unknown as Monitor;
    function Page() {
      return <AssistantPage a={useAssistant(m)} />;
    }
    try {
      const user = userEvent.setup();
      render(<Page />);
      const field = () => screen.getByLabelText("Mensagem para o assistente");
      const send = () =>
        user.click(screen.getByRole("button", { name: "Enviar mensagem" }));
      await user.type(field(), "Explique as estrelas");
      await send();
      expect(stream).toHaveBeenNthCalledWith(
        1,
        1,
        "Explique as estrelas",
        expect.anything(),
      );
      const saved = await screen.findByRole("button", {
        name: /Explique as estrelas.*Geral/,
      });
      expect(screen.getByText("Resposta local.")).toBeInTheDocument();

      await user.click(
        screen.getByRole("button", { name: "Sobre meu trabalho" }),
      );
      expect(screen.queryByText("Resposta local.")).not.toBeInTheDocument();
      await user.type(field(), "Responda sempre em tópicos");
      await send();
      expect(stream).toHaveBeenNthCalledWith(
        2,
        2,
        "Responda sempre em tópicos",
        expect.anything(),
      );
      expect(await screen.findByText("Regra aprendida.")).toBeInTheDocument();
      expect(
        screen.getByRole("button", {
          name: "Apagar regra: Responder em tópicos",
        }),
      ).toBeInTheDocument();

      await user.click(saved);
      expect(
        screen.getByRole("heading", { name: "Conversa geral" }),
      ).toBeInTheDocument();
      expect(screen.queryByText("Regra aprendida.")).not.toBeInTheDocument();
      await user.click(
        screen.getByRole("button", {
          name: "Excluir conversa: Explique as estrelas",
        }),
      );
      await user.click(screen.getByRole("button", { name: "Excluir" }));
      expect(calls).toHaveBeenCalledWith(
        "/assistant/conversations/1",
        "DELETE",
      );
      expect(
        screen.queryByRole("button", { name: /Explique as estrelas.*Geral/ }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Sobre o que vamos conversar?" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", {
          name: /Responda sempre em tópicos.*Trabalho/,
        }),
      ).toBeInTheDocument();
    } finally {
      stream.mockRestore();
      calls.mockRestore();
    }
  });
  it("suggests two replies, lets the user pick one and improves a selected passage", async () => {
    const calls = vi
      .spyOn(client, "api")
      .mockImplementation(async (path: string, method = "GET", body?: unknown) => {
        if (path === "/emails/7/draft" && method === "GET")
          return { body: "" } as never;
        if (path === "/emails/7/replies")
          return {
            options: ["Olá, Ana! Vi sim.", "Olá, Ana! Vi o material ontem e retorno até [data]."],
          } as never;
        if (path === "/emails/improve")
          return {
            options: [
              `direta:${(body as { text: string }).text}`,
              "Vi o material ontem",
            ],
          } as never;
        return undefined as never;
      });
    const m = {
      connected: true,
      prefs: { name: "Marcos" },
      setNotice: vi.fn(),
      setError: vi.fn(),
      fail: vi.fn(),
    } as unknown as Monitor;
    const email = {
      id: 7,
      account_id: 3,
      sender: "Ana Souza <ana@cliente.example>",
    } as client.Email;
    try {
      const user = userEvent.setup();
      render(<ReplyBox email={email} m={m} />);
      const improve = screen.getByRole("button", {
        name: "Melhorar trecho selecionado",
      });
      expect(improve).toBeDisabled();
      await user.type(
        screen.getByLabelText("O que você quer dizer? (opcional)"),
        "dizer que vi",
      );
      await user.click(
        screen.getByRole("button", { name: "Sugerir 2 respostas" }),
      );
      expect(calls).toHaveBeenCalledWith("/emails/7/replies", "POST", {
        instruction: "dizer que vi",
      });
      await user.click(
        await screen.findByRole("button", { name: "Usar opção 2" }),
      );
      const field = screen.getByLabelText("Sua resposta") as HTMLTextAreaElement;
      expect(field.value).toBe(
        "Olá, Ana! Vi o material ontem e retorno até [data].",
      );
      field.focus();
      field.setSelectionRange(10, 29);
      fireEvent.select(field);
      await user.click(improve);
      expect(calls).toHaveBeenCalledWith("/emails/improve", "POST", {
        text: "Vi o material ontem",
        draft: field.value,
        account_id: 3,
      });
      expect(await screen.findByText(/Trecho original:/)).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Usar versão 1" }));
      expect(field.value).toBe(
        "Olá, Ana! direta:Vi o material ontem e retorno até [data].",
      );
      expect(screen.queryByText(/Trecho original:/)).not.toBeInTheDocument();
    } finally {
      calls.mockRestore();
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
