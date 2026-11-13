import { invoke, isTauri } from "@tauri-apps/api/core";

export type Demand = {
  id: number;
  title: string;
  front_id: number;
  contact: string;
  channel: string;
  stage: string;
  priority: string;
  due: string | null;
  next_action: string;
  return_date: string | null;
  summary: string;
  origin_ref?: string;
};
export type Importance = "acao" | "importante" | "revisar" | "info";
export type Analysis = {
  categoria: string;
  importancia: Importance;
  motivo: string;
  resumo: string;
  acao_sugerida: string | null;
  prazo_texto: string | null;
  prazo_iso: string | null;
  trecho_prazo: string | null;
  confianca: number;
  modelo: string;
  correcao: string | null;
  provisional: boolean;
};
export type Email = {
  id: number;
  account_id: number;
  account: string;
  front_id: number;
  sender: string;
  subject: string;
  date: string | null;
  body: string;
  has_attachments: boolean;
  analysis_status: string;
  analysis: Analysis | null;
  demand_id: number | null;
  suggestion_id: number | null;
};
export type Suggestion = {
  id: number;
  email_id: number;
  front_id: number;
  title: string;
  contact: string;
  summary: string;
  due: string | null;
};
export type Account = {
  id: number;
  front_id: number;
  address: string;
  host: string;
  port: number;
  username: string;
  status: string;
  status_detail: string;
  last_sync: string | null;
};
export type AccountInput = {
  front_id: number;
  address: string;
  host: string;
  port: number;
  username: string;
  password: string;
};
export type WritingStyle = {
  account_id: number;
  address: string;
  front_id: number;
  sent: number;
  profile: string;
  greeting: string;
  closing: string;
  words: number;
  edited: boolean;
  updated_at: string | null;
  sent_status: string;
};
export type Storage = {
  files_dir: string | null;
  source: string | null;
  ready: boolean;
  in_onedrive: boolean;
  last_backup: string | null;
  suggestion: string;
};
export type Ollama = { available: boolean; models: string[] };
export type AppSettings = { model: string; priority_senders: string[] };

export const stages = {
  novo: "Novo",
  qualificacao: "Em qualificação",
  preparar_proposta: "Preparar proposta",
  proposta_enviada: "Proposta enviada",
  acompanhar: "Acompanhar",
  ganho: "Ganho",
  perdido: "Perdido",
};
export const importanceLabels: Record<Importance, string> = {
  acao: "Precisa de ação",
  importante: "Importante",
  revisar: "Revisar",
  info: "Informativo",
};
export const categoryLabels: Record<string, string> = {
  orcamento: "Orçamento",
  cliente: "Cliente",
  financeiro: "Financeiro",
  fornecedor: "Fornecedor",
  publicidade: "Publicidade",
  informativo: "Informativo",
  outro: "Outro",
};

export type Connection = { port: number; token: string };
let connection: Connection | null = null;
export function setConnection(value: Connection) {
  connection = value;
}
export async function connect() {
  if (isTauri()) {
    connection = await invoke<Connection>("connection");
    for (let attempt = 0; attempt < 30; attempt++) {
      try {
        await api("/health");
        return;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }
    throw new Error("O backend está iniciando. Tente conectar novamente.");
  }
  throw new Error(
    "Abra o aplicativo desktop. A prévia de navegador não se conecta ao banco real.",
  );
}
function request(path: string, method: string, body?: unknown) {
  if (!connection) throw new Error("Backend indisponível.");
  return fetch(`http://127.0.0.1:${connection.port}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${connection.token}`,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
/** Envia a gravação ao backend, que transcreve com o modelo local. */
export async function transcribe(audio: Blob): Promise<string> {
  if (!connection) throw new Error("Backend indisponível.");
  const response = await fetch(
    `http://127.0.0.1:${connection.port}/assistant/transcribe`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${connection.token}`,
        "Content-Type": audio.type || "audio/webm",
      },
      body: audio,
    },
  );
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "Não foi possível transcrever o áudio.",
    );
  return String(body?.text ?? "");
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await request(path, method, body);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : "Verifique os campos preenchidos e tente novamente.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export type Preferences = {
  name: string;
  tagline: string;
  avatar: string;
  fronts: string[];
  front_icons: string[];
  primary: string;
  accent: string;
};
export type SocialProfile = {
  id: number;
  front_id: number;
  network: string;
  username: string;
  name: string;
  avatar: string;
  status: string;
  status_detail: string;
  last_sync: string | null;
  followers: number | null;
  posts: number | null;
  followers_change: number | null;
  change_days: number;
  posts_week: number | null;
  stories_week: number | null;
  likes_week: number | null;
  comments_week: number | null;
  method?: "api" | "browser";
  enabled?: boolean;
  auto_demands?: boolean;
  browser_path?: string;
  comments_detail?: string;
};
export type BrowserProfile = {
  account_id: number;
  name: string;
  username: string;
  path: string;
};
export type SocialComment = {
  id: number;
  profile_id: number;
  front_id: number;
  author: string;
  text: string;
  post_url: string;
  published_at: string;
  status: string;
  reason: string;
  demand_id: number | null;
};
export type Calendar = {
  client_id: string;
  configured: boolean;
  connected: boolean;
  email: string;
  last_sync: string | null;
  error: string;
  events: number;
};
export type Attachment = {
  id: number;
  name: string;
  kind: string;
  size: number;
  chars: number;
  pages: number;
  truncated: boolean;
};
export type VoiceStatus = {
  size: string;
  sizes: { id: string; label: string; mb: number }[];
  engine: boolean;
  ready: boolean;
  downloading: boolean;
  progress: number;
  error: string;
};
export type Conversation = {
  id: number;
  mode: "work" | "general";
  title: string;
  updated_at: string;
};
export type AssistantRule = { id: number; text: string; source: string };
export type ChatAction = {
  kind: "reminder" | "demand";
  id: number;
  operation: string;
  text: string;
  when?: string;
  timezone?: string;
};
/** Envia uma pergunta a uma conversa salva e acompanha a resposta em partes. */
export async function conversationStream(
  id: number,
  content: string,
  on: {
    delta: (text: string) => void;
    rule: (rule: AssistantRule) => void;
    done: (conversation?: Conversation) => void;
    action?: (result: ChatAction) => void;
    front_id?: number;
    attachments?: number[];
    task?: "next_messages";
  },
) {
  const response = await request(
    `/assistant/conversations/${id}/messages`,
    "POST",
    {
      content,
      ...(on.front_id ? { front_id: on.front_id } : {}),
      ...(on.attachments?.length ? { attachments: on.attachments } : {}),
      ...(on.task ? { task: on.task } : {}),
    },
  );
  if (!response.ok || !response.body)
    throw new Error("Não foi possível enviar a pergunta.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "",
    finished = false;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const item = JSON.parse(line);
      if (item.error) throw new Error(item.error);
      if (item.delta) on.delta(item.delta);
      if (item.rule) on.rule(item.rule);
      if (item.action) on.action?.(item.action);
      if (item.done) {
        finished = true;
        on.done(item.conversation);
      }
    }
    if (done) break;
  }
  if (!finished)
    throw new Error(
      "A resposta foi interrompida. Reabra a conversa e tente novamente.",
    );
}
export async function pullModel(
  model: string,
  onProgress: (message: string) => void,
) {
  const response = await request("/ollama/pull", "POST", { model });
  if (!response.ok || !response.body)
    throw new Error("Não foi possível iniciar o download.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const item = JSON.parse(line);
      if (item.error) throw new Error(item.error);
      onProgress(
        item.total
          ? `${item.status} · ${Math.round((item.completed / item.total) * 100)}%`
          : item.status,
      );
    }
    if (done) break;
  }
}
