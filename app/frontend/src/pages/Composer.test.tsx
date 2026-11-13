import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api";
import type { ChatApi } from "./Assistant";
import { Composer } from "./Composer";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const makeChat = (extra: Record<string, unknown> = {}) =>
  ({
    mode: "general",
    conversationId: null,
    messages: [],
    busy: false,
    ready: true,
    preview: false,
    ask: vi.fn(),
    report: vi.fn(),
    refreshVoice: vi.fn(async () => ({ engine: true, ready: true, downloading: false })),
    openVoiceSettings: vi.fn(),
    ...extra,
  }) as unknown as ChatApi & Record<string, ReturnType<typeof vi.fn>>;

function backend() {
  let next = 1;
  return vi
    .spyOn(client, "api")
    .mockImplementation(async (path: string, _method?: string, body?: unknown) => {
      if (path === "/assistant/attachments") {
        const input = body as { name: string };
        return {
          id: next++,
          name: input.name,
          kind: /\.(png|jpg)$/.test(input.name) ? "image" : "text",
          size: 3,
          chars: 3,
          pages: 0,
          truncated: false,
        } as never;
      }
      return undefined as never;
    });
}

describe("composer attachments", () => {
  it("reads a file locally, shows it and sends it with a default request", async () => {
    const calls = backend();
    const chat = makeChat();
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    expect(screen.getByRole("button", { name: "Enviar mensagem" })).toBeDisabled();
    await user.upload(
      screen.getByLabelText("Escolher arquivos"),
      new File(["abc"], "notas.txt", { type: "text/plain" }),
    );
    expect(await screen.findByText("notas.txt")).toBeInTheDocument();
    expect(calls).toHaveBeenCalledWith("/assistant/attachments", "POST", {
      name: "notas.txt",
      data: "YWJj",
    });
    await user.click(await screen.findByRole("button", { name: "Enviar mensagem" }));
    expect(chat.ask).toHaveBeenCalledWith("Resuma o conteúdo deste arquivo.", {
      attachments: [expect.objectContaining({ id: 1, name: "notas.txt" })],
      task: undefined,
    });
    expect(screen.queryByText("notas.txt")).not.toBeInTheDocument();
  });

  it("offers to suggest the next messages for a conversation screenshot", async () => {
    backend();
    const chat = makeChat();
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    expect(screen.queryByRole("button", { name: /Sugerir próximas mensagens/ })).not.toBeInTheDocument();
    await user.upload(
      screen.getByLabelText("Escolher arquivos"),
      new File(["png"], "print.png", { type: "image/png" }),
    );
    await user.type(screen.getByLabelText("Mensagem para o assistente"), "quero fechar por 3.800");
    await user.click(await screen.findByRole("button", { name: /Sugerir próximas mensagens/ }));
    expect(chat.ask).toHaveBeenCalledWith("quero fechar por 3.800", {
      attachments: [expect.objectContaining({ name: "print.png", kind: "image" })],
      task: "next_messages",
    });
  });

  it("accepts a pasted screenshot, limits images and lets the user remove an attachment", async () => {
    const calls = backend();
    const chat = makeChat();
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    const field = screen.getByLabelText("Mensagem para o assistente");
    const paste = (name: string) => {
      const event = new Event("paste", { bubbles: true, cancelable: true }) as Event & { clipboardData: unknown };
      event.clipboardData = { files: [new File(["x"], name, { type: "image/png" })] };
      field.dispatchEvent(event);
    };
    paste("image.png");
    paste("segunda.png");
    paste("terceira.png");
    expect(await screen.findByText("segunda.png")).toBeInTheDocument();
    expect(chat.report).toHaveBeenCalledWith("Envie no máximo 2 imagens por mensagem.");
    expect(screen.queryByText("terceira.png")).not.toBeInTheDocument();
    expect(await screen.findByText(/^captura .*\.png$/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remover anexo: segunda.png" }));
    expect(calls).toHaveBeenCalledWith("/assistant/attachments/2", "DELETE");
    expect(screen.queryByText("segunda.png")).not.toBeInTheDocument();
  });

  it("shows a refusal from the server on the attachment chip", async () => {
    vi.spyOn(client, "api").mockRejectedValue(new Error("Tipo de arquivo não suportado."));
    const user = userEvent.setup({ applyAccept: false }); // arrastar um arquivo ignora o filtro do seletor
    render(<Composer chat={makeChat()} placeholder="Pergunte" />);
    await user.upload(
      screen.getByLabelText("Escolher arquivos"),
      new File(["MZ"], "programa.exe", { type: "application/octet-stream" }),
    );
    expect(await screen.findByText("Tipo de arquivo não suportado.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar mensagem" })).toBeDisabled();
  });

  it("is disabled in the browser preview", () => {
    render(<Composer chat={makeChat({ preview: true })} placeholder="Pergunte" />);
    expect(screen.getByRole("button", { name: "Anexar arquivo ou imagem" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Falar a mensagem" })).toBeDisabled();
  });
});

describe("composer dictation", () => {
  function stubMicrophone() {
    const tracks = [{ stop: vi.fn() }];
    const getUserMedia = vi.fn(async () => ({ getTracks: () => tracks }));
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
    class FakeRecorder {
      static isTypeSupported = () => true;
      state = "inactive";
      mimeType = "audio/webm;codecs=opus";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["audio"]) });
        this.onstop?.();
      }
    }
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    return { getUserMedia, tracks };
  }

  it("records, transcribes locally and puts the text in the box for review", async () => {
    const { getUserMedia, tracks } = stubMicrophone();
    const transcribe = vi.spyOn(client, "transcribe").mockResolvedValue("Preciso de um orçamento");
    const chat = makeChat();
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    const field = screen.getByLabelText("Mensagem para o assistente") as HTMLTextAreaElement;
    await user.type(field, "Oi,");
    await user.click(screen.getByRole("button", { name: "Falar a mensagem" }));
    expect(await screen.findByText(/Gravando… 0:00/)).toBeInTheDocument();
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    await user.click(screen.getAllByRole("button", { name: "Parar e transcrever" })[0]);
    await vi.waitFor(() => expect(field.value).toBe("Oi, Preciso de um orçamento"));
    expect(transcribe).toHaveBeenCalledWith(expect.objectContaining({ type: "audio/webm;codecs=opus" }));
    expect(tracks[0].stop).toHaveBeenCalled(); // o microfone é liberado
    expect(chat.ask).not.toHaveBeenCalled(); // nada é enviado sem revisão
  });

  it("discards a cancelled recording", async () => {
    stubMicrophone();
    const transcribe = vi.spyOn(client, "transcribe");
    const user = userEvent.setup();
    render(<Composer chat={makeChat()} placeholder="Pergunte" />);
    await user.click(screen.getByRole("button", { name: "Falar a mensagem" }));
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    expect(transcribe).not.toHaveBeenCalled();
    expect(screen.queryByText(/Gravando/)).not.toBeInTheDocument();
  });

  it("asks to download the voice model first and never opens the microphone without it", async () => {
    const { getUserMedia } = stubMicrophone();
    const chat = makeChat({ refreshVoice: vi.fn(async () => ({ engine: true, ready: false, downloading: false })) });
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    await user.click(screen.getByRole("button", { name: "Falar a mensagem" }));
    expect(await screen.findByText(/baixe antes o modelo de voz/)).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Configurar voz" }));
    expect(chat.openVoiceSettings).toHaveBeenCalled();
  });

  it("explains a blocked microphone and a transcription failure", async () => {
    const getUserMedia = vi.fn(async () => {
      throw new DOMException("negado", "NotAllowedError");
    });
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
    vi.stubGlobal("MediaRecorder", class {});
    const chat = makeChat();
    const user = userEvent.setup();
    render(<Composer chat={chat} placeholder="Pergunte" />);
    await user.click(screen.getByRole("button", { name: "Falar a mensagem" }));
    await vi.waitFor(() =>
      expect(chat.report).toHaveBeenCalledWith(expect.stringContaining("Privacidade e segurança")),
    );
  });
});
