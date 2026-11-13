import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Chat, ChatApi } from "./Assistant";
import {
  AssistantRecords,
  AssistantSkills,
  ResponseMetrics,
} from "./AssistantTools";
import * as client from "../api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("delivers real streamed metrics to the chat callback", async () => {
  client.setConnection({ port: 14620, token: "synthetic-test" });
  const encoder = new TextEncoder();
  const data =
    [
      { delta: "Resposta" },
      { done: true, metrics: { tokens_per_second: 24, output_tokens: 48 } },
    ]
      .map((item) => JSON.stringify(item))
      .join("\n") + "\n";
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(data.slice(0, 17)));
              controller.enqueue(encoder.encode(data.slice(17)));
              controller.close();
            },
          }),
        ),
    ),
  );
  const on = { delta: vi.fn(), rule: vi.fn(), done: vi.fn(), metrics: vi.fn() };
  await client.conversationStream(1, "Oi", on);
  expect(on.metrics).toHaveBeenCalledWith({
    tokens_per_second: 24,
    output_tokens: 48,
  });
  expect(on.delta).toHaveBeenCalledWith("Resposta");
  expect(on.done).toHaveBeenCalledOnce();
});

it("opens an image already sent in chat, zooms it and closes with Escape", async () => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
  const calls = vi.spyOn(client, "api").mockResolvedValue({
    src: "data:image/png;base64,YWJj",
    size: 123,
  } as never);
  const chat = {
    mode: "general",
    messages: [
      {
        role: "user",
        text: "Veja",
        attachments: [{ id: 7, name: "print.png", kind: "image" }],
      },
    ],
    busy: false,
    ready: true,
    preview: false,
    ask: vi.fn(),
    report: vi.fn(),
    available: true,
  } as unknown as ChatApi;
  const user = userEvent.setup();
  render(<Chat chat={chat} />);
  await user.click(
    screen.getByRole("button", { name: "Abrir imagem: print.png" }),
  );
  const image = await screen.findByRole("img", { name: "print.png" });
  expect(calls).toHaveBeenCalledWith("/assistant/attachments/7/preview");
  await user.click(screen.getByRole("button", { name: "Ampliar imagem" }));
  expect(image).toHaveStyle({ width: "125%" });
  await user.click(screen.getByRole("button", { name: "Ajustar à tela" }));
  expect(image).toHaveStyle({ width: "100%" });
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows generation speed separately from load time and never invents absent speed", async () => {
  const { rerender } = render(
    <ResponseMetrics
      value={{
        tokens_per_second: 24,
        output_tokens: 48,
        load_seconds: 8,
        generation_seconds: 2,
      }}
    />,
  );
  expect(screen.getByText(/24 tk\/s/)).toBeInTheDocument();
  await userEvent.click(screen.getByText(/24 tk\/s/));
  expect(screen.getByText("8 s")).toBeVisible();
  rerender(<ResponseMetrics value={{ output_tokens: 48 }} />);
  expect(screen.queryByText(/\d+ tk\/s/)).not.toBeInTheDocument();
});

it("shows last activity, model VRAM and opens the associated conversation", async () => {
  vi.spyOn(client, "api").mockImplementation(async (path) =>
    path === "/assistant/records"
      ? ([
          {
            id: 1,
            conversation_id: 3,
            kind: "chat",
            model: "qwen3.5:4b-q4_K_M",
            detail: "Resposta concluída",
            status: "completed",
            created_at: "2026-11-13T12:00:00",
            metrics: { tokens_per_second: 24 },
            skills: ["Leitura cuidadosa de imagens"],
          },
        ] as never)
      : ({
          model: "qwen3.5:4b-q4_K_M",
          context: 16384,
          keep_alive: "30m",
          available: true,
          loaded: [
            {
              name: "qwen3.5:4b-q4_K_M",
              size: 3 * 1024 ** 3,
              size_vram: 3 * 1024 ** 3,
              context_length: 16384,
            },
          ],
        } as never),
  );
  const open = vi.fn();
  render(<AssistantRecords connected openConversation={open} />);
  expect(await screen.findByText("3 GiB")).toBeInTheDocument();
  expect(
    screen.getByText("Leitura cuidadosa de imagens", { exact: false }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Abrir conversa" }));
  expect(open).toHaveBeenCalledWith(3);
});

it("can disable a skill and create a custom skill without changing models", async () => {
  const skill = {
    id: "vision",
    name: "Leitura de imagens",
    enabled: true,
    builtin: true,
    keywords: "imagem",
    instructions: "Confira os textos",
  };
  const calls = vi
    .spyOn(client, "api")
    .mockImplementation(async (path, method, body) => {
      if (method === "PUT") return [{ ...skill, enabled: false }] as never;
      if (method === "POST")
        return {
          ...(body as object),
          id: "custom-1",
          enabled: true,
          builtin: false,
        } as never;
      return [skill] as never;
    });
  const user = userEvent.setup();
  render(<AssistantSkills connected />);
  await user.click(
    await screen.findByRole("checkbox", { name: "Leitura de imagens" }),
  );
  expect(calls).toHaveBeenCalledWith("/assistant/skills/vision", "PUT", {
    enabled: false,
  });
  await user.type(screen.getByLabelText("Nome"), "Revisar contratos");
  await user.type(
    screen.getByLabelText("Palavras-chave separadas por vírgula"),
    "contrato",
  );
  await user.type(
    screen.getByLabelText("Instruções"),
    "Confira as datas e os valores do contrato.",
  );
  await user.click(screen.getByRole("button", { name: "Adicionar skill" }));
  expect(
    await screen.findByRole("checkbox", { name: "Revisar contratos" }),
  ).toBeChecked();
  expect(calls.mock.calls.some(([path]) => path === "/settings")).toBe(false);
});

it("imports Markdown as a reviewable draft, preserves its original and supports editing", async () => {
  const original = "# Escrita natural\n" + "Referência completa. ".repeat(500);
  const active = "Reescreva mantendo valores, nomes e datas. ".repeat(20);
  const draft = {
    name: "Escrita natural",
    description: "Revisar textos",
    keywords: "reescrev",
    instructions: active,
    source_markdown: original,
    source_name: "SKILL.md",
    warnings: [],
  };
  const calls = vi
    .spyOn(client, "api")
    .mockImplementation(async (path, method, body) => {
      if (path === "/assistant/skills/import") return draft as never;
      if (method === "POST" || method === "PATCH")
        return {
          ...(body as object),
          id: "custom-2",
          enabled: true,
          builtin: false,
        } as never;
      return [] as never;
    });
  const user = userEvent.setup();
  render(<AssistantSkills connected />);
  await user.upload(
    screen.getByLabelText("Escolher arquivo de skill"),
    new File([original], "SKILL.md", { type: "text/markdown" }),
  );
  expect(
    await screen.findByDisplayValue("Escrita natural"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Instruções")).toHaveValue(active);
  expect(
    calls.mock.calls.filter(([, method]) => method === "POST"),
  ).toHaveLength(1); // prévia; não instala automaticamente
  await user.click(screen.getByRole("button", { name: "Adicionar skill" }));
  await user.click(
    await screen.findByRole("button", {
      name: "Editar skill: Escrita natural",
    }),
  );
  await user.clear(screen.getByLabelText("Instruções"));
  await user.type(
    screen.getByLabelText("Instruções"),
    "Preserve os números e remova os clichês.",
  );
  await user.click(
    screen.getByRole("button", { name: "Salvar alterações da skill" }),
  );
  expect(calls).toHaveBeenCalledWith(
    "/assistant/skills/custom-2",
    "PATCH",
    expect.objectContaining({
      source_markdown: original,
      instructions: "Preserve os números e remova os clichês.",
    }),
  );
});
