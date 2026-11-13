import {
  ArrowRight,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  Mic,
  Paperclip,
  Square,
  Wand2,
  X,
} from "lucide-react";
import { ClipboardEvent, DragEvent, useEffect, useRef, useState } from "react";
import { api, Attachment, transcribe } from "../api";
import type { ChatApi } from "./Assistant";
import { Callout } from "../ui";

const MAX_FILES = 5;
const MAX_IMAGES = 2;
const MAX_BYTES = 10 * 1024 * 1024;
const IMAGE_SIDE = 1568;
const RECORD_LIMIT = 180;
const ACCEPT =
  ".txt,.md,.csv,.tsv,.json,.log,.eml,.xml,.html,.htm,.pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.gif";

type Prepared = { name: string; data: string; thumb?: string };
type Pending = {
  key: number;
  name: string;
  image: boolean;
  thumb?: string;
  status: "uploading" | "ready" | "error";
  attachment?: Attachment;
  error?: string;
};

function toBase64(bytes: Uint8Array) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000)
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}
const readBytes = (blob: Blob) =>
  new Promise<Uint8Array>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
const canvasBlob = (canvas: HTMLCanvasElement, quality: number) =>
  new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", quality),
  );

/** Capturas grandes são reduzidas e viram JPEG: o modelo lê igual e a resposta chega bem mais rápido. */
async function prepareImage(file: File): Promise<Prepared> {
  const name = /^image\.(png|jpe?g)$/i.test(file.name)
    ? `captura ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }).replace(":", "h")}.png`
    : file.name;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, IMAGE_SIDE / Math.max(bitmap.width, bitmap.height));
    const draw = (width: number, height: number) => {
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width));
      canvas.height = Math.max(1, Math.round(height));
      const context = canvas.getContext("2d")!;
      context.fillStyle = "#fff"; // PNG com transparência não pode virar preto
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      return canvas;
    };
    const full = await canvasBlob(draw(bitmap.width * scale, bitmap.height * scale), 0.88);
    const small = draw(72, (72 * bitmap.height) / bitmap.width);
    if (!full) throw new Error("sem conversão");
    return {
      name: name.replace(/\.[^.]+$/, "") + ".jpg",
      data: toBase64(await readBytes(full)),
      thumb: small.toDataURL("image/jpeg", 0.7),
    };
  } catch {
    // Sem decodificador no ambiente: envia o original quando o servidor consegue ler.
    if (/^image\/(png|jpeg)$/.test(file.type) && file.size <= 6 * 1024 * 1024)
      return { name, data: toBase64(await readBytes(file)) };
    throw new Error(`${name}: não consegui ler esta imagem. Use PNG ou JPEG.`);
  }
}
async function prepare(file: File): Promise<Prepared> {
  if (file.size > MAX_BYTES)
    throw new Error(`${file.name}: o arquivo passa de 10 MB.`);
  if (file.type.startsWith("image/")) return prepareImage(file);
  return { name: file.name, data: toBase64(await readBytes(file)) };
}

type Phase = "idle" | "recording" | "transcribing";
/** Grava a voz no próprio aplicativo e transcreve com o modelo local do backend. */
function useDictation(onText: (text: string) => void, onProblem: (text: string) => void) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const discard = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const elapsed = useRef(0);

  function stop(keep = true) {
    discard.current = !keep;
    window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }
  useEffect(() => () => stop(false), []);
  useEffect(() => {
    if (phase !== "recording") return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && stop(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase]);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined")
      return onProblem("Este ambiente não permite gravar áudio.");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find(
        (item) => MediaRecorder.isTypeSupported?.(item),
      );
      const rec = new MediaRecorder(media, type ? { mimeType: type } : undefined);
      chunks.current = [];
      discard.current = false;
      rec.ondataavailable = (event) => event.data.size && chunks.current.push(event.data);
      rec.onstop = async () => {
        media.getTracks().forEach((track) => track.stop());
        window.clearInterval(timer.current);
        if (discard.current || !chunks.current.length) return setPhase("idle");
        setPhase("transcribing");
        try {
          const text = await transcribe(new Blob(chunks.current, { type: rec.mimeType || "audio/webm" }));
          if (text.trim()) onText(text.trim());
          else onProblem("Não ouvi nada nesta gravação. Tente de novo, mais perto do microfone.");
        } catch (e) {
          onProblem((e as Error).message);
        } finally {
          setPhase("idle");
        }
      };
      recorder.current = rec;
      rec.start();
      elapsed.current = 0;
      setSeconds(0);
      setPhase("recording");
      timer.current = window.setInterval(() => {
        elapsed.current += 1;
        setSeconds(elapsed.current);
        if (elapsed.current >= RECORD_LIMIT) stop();
      }, 1000);
    } catch (e) {
      const name = (e as DOMException).name;
      onProblem(
        name === "NotAllowedError" || name === "SecurityError"
          ? "O microfone está bloqueado. Libere em Configurações do Windows › Privacidade e segurança › Microfone."
          : name === "NotFoundError"
            ? "Nenhum microfone foi encontrado neste computador."
            : "Não foi possível usar o microfone.",
      );
    }
  }
  return { phase, seconds, start, stop };
}
const clock = (total: number) =>
  `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;

export function Composer({ chat, placeholder }: { chat: ChatApi; placeholder: string }) {
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const [over, setOver] = useState(false);
  const [voiceHint, setVoiceHint] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const counter = useRef(0);
  const current = useRef(pending);
  current.current = pending;
  const dictation = useDictation(
    (text) => {
      setQuestion((old) => `${old.replace(/\s*$/, old.trim() ? " " : "")}${text}`.slice(0, 4000));
      field.current?.focus();
    },
    (text) => chat.report(text),
  );

  const discardUnsent = () => {
    for (const item of current.current)
      if (item.attachment) void api(`/assistant/attachments/${item.attachment.id}`, "DELETE").catch(() => {});
  };
  useEffect(() => {
    discardUnsent();
    setQuestion("");
    setPending([]);
    setVoiceHint("");
  }, [chat.mode, chat.conversationId]);

  async function addFiles(list: File[]) {
    if (!list.length || chat.preview) return;
    const free = MAX_FILES - current.current.length;
    if (free <= 0) return chat.report(`Anexe no máximo ${MAX_FILES} arquivos por mensagem.`);
    for (const file of list.slice(0, free)) {
      const isImage = file.type.startsWith("image/");
      if (isImage && current.current.filter((item) => item.image).length >= MAX_IMAGES) {
        chat.report(`Envie no máximo ${MAX_IMAGES} imagens por mensagem.`);
        continue;
      }
      const key = ++counter.current;
      const mark = (change: Partial<Pending>) =>
        setPending((old) => old.map((item) => (item.key === key ? { ...item, ...change } : item)));
      const entry: Pending = { key, name: file.name, image: isImage, status: "uploading" };
      current.current = [...current.current, entry];
      setPending(current.current);
      try {
        const prepared = await prepare(file);
        mark({ name: prepared.name, thumb: prepared.thumb });
        const attachment = await api<Attachment>("/assistant/attachments", "POST", {
          name: prepared.name,
          data: prepared.data,
        });
        mark({ status: "ready", attachment, name: attachment.name });
      } catch (e) {
        mark({ status: "error", error: (e as Error).message });
      }
    }
    if (list.length > free) chat.report(`Só ${free} arquivo(s) couberam; o limite é ${MAX_FILES} por mensagem.`);
  }
  function remove(item: Pending) {
    setPending((old) => old.filter((other) => other.key !== item.key));
    if (item.attachment)
      void api(`/assistant/attachments/${item.attachment.id}`, "DELETE").catch(() => {});
  }

  const ready = pending.filter((item) => item.status === "ready");
  const uploading = pending.some((item) => item.status === "uploading");
  function send(task?: "next_messages") {
    if (chat.busy || uploading) return;
    const typed = question.trim();
    const content =
      typed ||
      (task
        ? "Sugira as próximas mensagens para esta conversa."
        : ready.some((item) => item.image)
          ? "Descreva o que aparece nesta imagem."
          : ready.length
            ? "Resuma o conteúdo deste arquivo."
            : "");
    if (!content) return;
    void chat.ask(content, { attachments: ready.flatMap((item) => (item.attachment ? [item.attachment] : [])), task });
    setQuestion("");
    setPending([]);
  }
  async function microphone() {
    if (dictation.phase === "recording") return dictation.stop();
    if (dictation.phase !== "idle") return;
    setVoiceHint("");
    try {
      const status = await chat.refreshVoice();
      if (!status.engine) return chat.report("O motor de voz não está incluído nesta instalação.");
      if (!status.ready)
        return setVoiceHint(
          status.downloading
            ? "O modelo de voz ainda está sendo baixado. Acompanhe em Configurações."
            : "Para falar com o assistente, baixe antes o modelo de voz (uma vez, em Configurações). Ele roda neste computador.",
        );
    } catch (e) {
      return chat.report((e as Error).message);
    }
    void dictation.start();
  }
  const files = (event: DragEvent | ClipboardEvent) =>
    [...((event as DragEvent).dataTransfer ?? (event as ClipboardEvent).clipboardData)?.files ?? []];
  const hasImage = ready.some((item) => item.image);
  const recording = dictation.phase === "recording";

  return (
    <form
      className={`composer ${over ? "over" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
      onDragOver={(event) => {
        if (!chat.preview && [...event.dataTransfer.types].includes("Files")) {
          event.preventDefault();
          setOver(true);
        }
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        setOver(false);
        const dropped = files(event);
        if (dropped.length) {
          event.preventDefault();
          void addFiles(dropped);
        }
      }}
    >
      {voiceHint && (
        <Callout
          action={
            <button className="sm" type="button" onClick={chat.openVoiceSettings}>
              Configurar voz
            </button>
          }
        >
          {voiceHint}
        </Callout>
      )}
      {pending.length > 0 && (
        <div className="attach-row">
          {pending.map((item) => (
            <span
              key={item.key}
              className={`attach-chip ${item.status}`}
              title={item.error || item.attachment?.name || item.name}
            >
              {item.thumb ? (
                <img src={item.thumb} alt="" />
              ) : item.image ? (
                <ImageIcon size={16} aria-hidden />
              ) : (
                <FileText size={16} aria-hidden />
              )}
              <span className="attach-name">{item.name}</span>
              <small>
                {item.status === "uploading"
                  ? "Lendo…"
                  : item.status === "error"
                    ? item.error
                    : item.attachment?.truncated
                      ? "texto cortado"
                      : item.attachment?.pages
                        ? `${item.attachment.pages} pág.`
                        : ""}
              </small>
              {item.status === "uploading" && <LoaderCircle size={14} className="spin" aria-hidden />}
              <button
                type="button"
                className="icon sm ghost"
                aria-label={`Remover anexo: ${item.name}`}
                onClick={() => remove(item)}
              >
                <X size={14} />
              </button>
            </span>
          ))}
        </div>
      )}
      {dictation.phase !== "idle" && (
        <div className="recording" role="status">
          <span className="rec-dot" aria-hidden />
          {recording ? `Gravando… ${clock(dictation.seconds)}` : "Transcrevendo no seu computador…"}
          {recording && (
            <>
              <button type="button" className="sm" onClick={() => dictation.stop()}>
                Parar e transcrever
              </button>
              <button type="button" className="sm ghost" onClick={() => dictation.stop(false)}>
                Cancelar
              </button>
            </>
          )}
        </div>
      )}
      <textarea
        ref={field}
        aria-label="Mensagem para o assistente"
        placeholder={over ? "Solte o arquivo aqui" : placeholder}
        maxLength={4000}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onPaste={(event) => {
          const pasted = files(event);
          if (pasted.length) {
            event.preventDefault();
            void addFiles(pasted);
          }
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            send();
          }
        }}
      />
      <div className="composer-bar">
        <input
          ref={input}
          type="file"
          hidden
          multiple
          accept={ACCEPT}
          aria-label="Escolher arquivos"
          onChange={(event) => {
            void addFiles([...(event.target.files ?? [])]);
            event.target.value = "";
          }}
        />
        <button
          type="button"
          className="icon sm"
          aria-label="Anexar arquivo ou imagem"
          title={chat.preview ? "Disponível no aplicativo desktop" : "Anexar arquivo ou imagem (ou cole um print)"}
          disabled={chat.preview}
          onClick={() => input.current?.click()}
        >
          <Paperclip size={16} />
        </button>
        <button
          type="button"
          className={`icon sm ${recording ? "danger" : ""}`}
          aria-label={recording ? "Parar e transcrever" : "Falar a mensagem"}
          aria-pressed={recording}
          title={chat.preview ? "Disponível no aplicativo desktop" : recording ? "Parar e transcrever" : "Falar a mensagem"}
          disabled={chat.preview || dictation.phase === "transcribing"}
          onClick={() => void microphone()}
        >
          {recording ? <Square size={16} /> : <Mic size={16} />}
        </button>
        {ready.length > 0 && (
          <button
            type="button"
            className="sm"
            disabled={chat.busy || uploading}
            title={hasImage ? "Lê a conversa do print e sugere o que responder" : "Lê a conversa e sugere o que responder"}
            onClick={() => send("next_messages")}
          >
            <Wand2 size={16} />
            Sugerir próximas mensagens
          </button>
        )}
        <span className="grow" />
        <button
          className="icon sm primary"
          aria-label="Enviar mensagem"
          disabled={chat.busy || uploading || (!question.trim() && !ready.length)}
        >
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
}
