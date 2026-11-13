import {
  ArrowUpRight,
  Briefcase,
  CheckCircle2,
  FileText,
  Image as ImageIcon,
  MessageSquare,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  api,
  AssistantRule,
  Attachment,
  ChatAction,
  Conversation,
  conversationStream,
  VoiceStatus,
} from "../api";
import { Composer } from "./Composer";
import type { Monitor } from "../store";
import { Callout, timeLabel } from "../ui";

const OFFLINE =
  "Na prévia do navegador o assistente não fala com o modelo. Abra o aplicativo desktop para conversar.";

export type ChatMode = "work" | "general";
type ChatMessage = {
  role: "user" | "assistant" | "rule";
  text: string;
  error?: boolean;
  action?: ChatAction;
  attachments?: { id: number; name: string; kind: string }[];
};
const draft = (mode: ChatMode) => `new-${mode}`;

/** Conversas salvas no banco local, separadas por modo, e as regras que o assistente aprendeu. */
export function useAssistant(m: Monitor) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [rules, setRules] = useState<AssistantRule[]>([]);
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({});
  const [active, setActive] = useState<Record<ChatMode, number | null>>({
    work: null,
    general: null,
  });
  const [busy, setBusy] = useState<Record<ChatMode, boolean>>({
    work: false,
    general: false,
  });
  const [view, setView] = useState<ChatMode>("general");
  const selection = useRef(0);
  const { connected, fail } = m;
  const ready = connected && !!m.ollama?.models.includes(m.settings.model);

  useEffect(() => {
    if (!connected) return;
    Promise.all([
      api<Conversation[]>("/assistant/conversations"),
      api<AssistantRule[]>("/assistant/rules"),
    ])
      .then(([list, learned]) => {
        setConversations(list);
        setRules(learned);
      })
      .catch(fail);
  }, [connected]);

  const append = (key: string, items: ChatMessage[]) =>
    setThreads((old) => ({ ...old, [key]: [...(old[key] || []), ...items] }));
  const patchAnswer = (
    key: string,
    change: (message: ChatMessage) => ChatMessage,
  ) =>
    setThreads((old) => {
      const list = old[key] || [];
      const index = list.map((item) => item.role).lastIndexOf("assistant");
      return index < 0
        ? old
        : {
            ...old,
            [key]: list.map((item, i) => (i === index ? change(item) : item)),
          };
    });

  const [voice, setVoice] = useState<VoiceStatus | null>(null);
  async function refreshVoice() {
    const status = await api<VoiceStatus>("/voice");
    setVoice(status);
    return status;
  }
  async function ask(
    mode: ChatMode,
    text: string,
    options: { attachments?: Attachment[]; task?: "next_messages" } = {},
  ) {
    const question = text.trim();
    if (!question || busy[mode] || question.length > 4000) return;
    if (!connected) {
      append(draft(mode), [
        { role: "user", text: question },
        { role: "assistant", text: OFFLINE },
      ]);
      return;
    }
    setBusy((old) => ({ ...old, [mode]: true }));
    let key = "";
    try {
      let id = active[mode];
      if (id === null) {
        id = (
          await api<Conversation>("/assistant/conversations", "POST", { mode })
        ).id;
        const created = id;
        setActive((old) => ({ ...old, [mode]: created }));
      }
      key = String(id);
      const sent = options.attachments ?? [];
      append(key, [
        {
          role: "user",
          text: question,
          ...(sent.length
            ? {
                attachments: sent.map(({ id, name, kind }) => ({
                  id,
                  name,
                  kind,
                })),
              }
            : {}),
        },
        { role: "assistant", text: "" },
      ]);
      await conversationStream(id, question, {
        front_id: m.front || undefined,
        attachments: sent.map((item) => item.id),
        task: options.task,
        delta: (part) =>
          patchAnswer(key, (last) => ({ ...last, text: last.text + part })),
        rule: (rule) => {
          setRules((old) => [rule, ...old.filter((r) => r.id !== rule.id)]);
          append(key, [{ role: "rule", text: rule.text }]);
        },
        action: (result) => {
          patchAnswer(key, (last) => ({ ...last, action: result }));
          void m.refreshDemands?.().catch(m.fail);
        },
        done: (conversation) => {
          if (conversation)
            setConversations((old) => [
              conversation,
              ...old.filter((item) => item.id !== conversation.id),
            ]);
        },
      });
    } catch (e) {
      const message = (e as Error).message;
      if (key)
        patchAnswer(key, (last) => ({
          role: "assistant",
          text: last.text ? `${last.text}\n\n${message}` : message,
          error: true,
        }));
      else fail(e);
      void api<Conversation[]>("/assistant/conversations")
        .then(setConversations)
        .catch(() => {});
    } finally {
      setBusy((old) => ({ ...old, [mode]: false }));
    }
  }

  async function open(conversation: Conversation) {
    if (busy[conversation.mode]) return;
    const request = ++selection.current;
    try {
      const key = String(conversation.id);
      if (!threads[key]) {
        const messages = await api<ChatMessage[]>(
          `/assistant/conversations/${conversation.id}/messages`,
        );
        if (request !== selection.current) return;
        setThreads((old) => (old[key] ? old : { ...old, [key]: messages }));
      }
      if (request !== selection.current) return;
      setActive((old) => ({ ...old, [conversation.mode]: conversation.id }));
      setView(conversation.mode);
    } catch (e) {
      fail(e);
    }
  }
  function startNew(mode: ChatMode) {
    if (busy[mode]) return;
    selection.current++;
    setActive((old) => ({ ...old, [mode]: null }));
    setThreads((old) => ({ ...old, [draft(mode)]: [] }));
    setView(mode);
  }
  async function remove(conversation: Conversation) {
    try {
      await api(`/assistant/conversations/${conversation.id}`, "DELETE");
      setConversations((old) =>
        old.filter((item) => item.id !== conversation.id),
      );
      setActive((old) =>
        old[conversation.mode] === conversation.id
          ? { ...old, [conversation.mode]: null }
          : old,
      );
      selection.current++;
      setThreads((old) => {
        const copy = { ...old };
        delete copy[String(conversation.id)];
        return copy;
      });
      m.setNotice("Conversa excluída.");
    } catch (e) {
      fail(e);
    }
  }
  async function addRule(text: string) {
    try {
      const rule = await api<AssistantRule>("/assistant/rules", "POST", {
        text,
      });
      setRules((old) => [rule, ...old]);
      return true;
    } catch (e) {
      fail(e);
      return false;
    }
  }
  async function removeRule(rule: AssistantRule) {
    try {
      await api(`/assistant/rules/${rule.id}`, "DELETE");
      setRules((old) => old.filter((item) => item.id !== rule.id));
    } catch (e) {
      fail(e);
    }
  }

  const chat = (mode: ChatMode) => ({
    mode,
    conversationId: active[mode],
    messages:
      threads[active[mode] === null ? draft(mode) : String(active[mode])] || [],
    busy: busy[mode],
    ready,
    ask: (
      text: string,
      options?: { attachments?: Attachment[]; task?: "next_messages" },
    ) => ask(mode, text, options),
    report: (text: string) => m.setError(text),
    refreshVoice,
    voice,
    openVoiceSettings: () => m.setPage("Configurações"),
    clear: () => startNew(mode),
    openSettings: () => m.setPage("Configurações"),
    openDemand: (id: number) => {
      const demand = m.demands.find((item) => item.id === id);
      if (demand) m.setDetail(demand);
      return !!demand;
    },
    hasDemand: (id: number) => m.demands.some((item) => item.id === id),
    openAction: (result: ChatAction) => {
      if (result.kind === "reminder") m.setPage("Lembretes");
      else {
        const demand = m.demands.find((item) => item.id === result.id);
        if (demand) m.setDetail(demand);
        else m.setPage("Demandas");
      }
    },
    preview: !connected,
    available: !!m.ollama?.available,
    model: m.settings.model,
  });
  return {
    work: chat("work"),
    general: chat("general"),
    view,
    conversations,
    rules,
    open,
    startNew,
    remove,
    addRule,
    removeRule,
    connected,
    openPage: () => {
      setView("work");
      m.setPage("Assistente");
    },
  };
}
export type Assistant = ReturnType<typeof useAssistant>;
export type ChatApi = Assistant["work"];

/** Transforma citações como [D12] em atalhos para a demanda. */
function Answer({ text, chat }: { text: string; chat: ChatApi }) {
  if (chat.mode !== "work") return <>{text}</>;
  return (
    <>
      {text.split(/(\[D\d+\])/g).map((part, i) => {
        const id = Number(/^\[D(\d+)\]$/.exec(part)?.[1]);
        return id && chat.hasDemand(id) ? (
          <button
            key={i}
            className="cite"
            title="Abrir demanda"
            onClick={() => chat.openDemand(id)}
          >
            {part}
          </button>
        ) : (
          part
        );
      })}
    </>
  );
}

export function Chat({
  chat,
  compact = false,
}: {
  chat: ChatApi;
  compact?: boolean;
}) {
  const general = chat.mode === "general";
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => {
    log.current?.scrollTo?.({ top: log.current.scrollHeight });
  }, [chat.messages]);
  function send(text: string) {
    if (chat.busy || !text.trim()) return;
    void chat.ask(text);
  }
  return (
    <div className="chat">
      {chat.messages.length === 0 && (
        <div className="chat-intro">
          <h3>
            {general
              ? "Sobre o que vamos conversar?"
              : "Um pouco mais de clareza."}
          </h3>
          <p>
            {general
              ? "Um espaço para tirar dúvidas, explorar ideias, escrever ou aprender sobre qualquer assunto com a sua IA local. Cada conversa fica salva neste computador."
              : "Consulte seus dados ou peça uma ação: criar uma demanda, registrar um lembrete, reagendar ou concluir. Informe data e horário para lembretes e a frente para demandas."}
          </p>
        </div>
      )}
      {!chat.preview && !chat.ready && (
        <Callout
          action={
            <button className="sm" onClick={chat.openSettings}>
              Configurar
            </button>
          }
        >
          {chat.available
            ? `O modelo ${chat.model} ainda não foi baixado.`
            : "O Ollama não respondeu. Abra o Ollama e verifique de novo em Configurações."}{" "}
          Pedidos diretos de lembretes e demandas continuam disponíveis.
        </Callout>
      )}
      <div className="chat-log" aria-live="polite" ref={log}>
        {chat.messages.map((message, i) =>
          message.role === "rule" ? (
            <div key={i} className="message message-rule">
              <Sparkles size={16} aria-hidden />
              <span>
                <strong>Regra aprendida.</strong> {message.text}
              </span>
            </div>
          ) : (
            <div
              key={i}
              className={`message message-${message.role} ${message.error ? "error" : ""}`}
            >
              {message.role === "assistant" && !message.error ? (
                message.text ? (
                  <>
                    <Answer text={message.text} chat={chat} />
                    {message.action && (
                      <div className="chat-action-result">
                        <span>
                          <CheckCircle2 size={16} aria-hidden /> Resultado
                          registrado
                        </span>
                        <button
                          className="sm"
                          onClick={() => chat.openAction(message.action!)}
                        >
                          {message.action.kind === "reminder"
                            ? "Abrir lembretes"
                            : "Abrir demanda"}
                          <ArrowUpRight size={16} aria-hidden />
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  "Pensando…"
                )
              ) : (
                <>
                  {message.attachments?.length ? (
                    <span className="attach-row sent">
                      {message.attachments.map((file) => (
                        <span className="attach-chip static" key={file.id}>
                          {file.kind === "image" ? (
                            <ImageIcon size={16} aria-hidden />
                          ) : (
                            <FileText size={16} aria-hidden />
                          )}
                          <span className="attach-name">{file.name}</span>
                        </span>
                      ))}
                    </span>
                  ) : null}
                  {message.text}
                </>
              )}
            </div>
          ),
        )}
      </div>
      {chat.messages.length === 0 && (
        <div className="prompts">
          {(general
            ? [
                "Me ajude a desenvolver uma ideia",
                "Explique um assunto de forma simples",
              ]
            : ["O que priorizar hoje?", "Crie um lembrete para amanhã às 9h"]
          ).map((prompt) => (
            <button
              key={prompt}
              disabled={chat.busy}
              onClick={() => send(prompt)}
            >
              {prompt}
              <ArrowUpRight size={16} />
            </button>
          ))}
        </div>
      )}
      <Composer
        chat={chat}
        placeholder={
          general
            ? "Converse sobre qualquer assunto…"
            : "Pergunte ou peça uma ação…"
        }
      />
      <div className="chat-foot">
        <small>
          IA local · pedidos diretos podem criar e alterar registros
        </small>
        {compact && chat.messages.length > 0 && (
          <button className="link" disabled={chat.busy} onClick={chat.clear}>
            Nova conversa
          </button>
        )}
      </div>
    </div>
  );
}

export function AssistantHeader({ a }: { a: Assistant }) {
  return (
    <header>
      <div>
        <Sparkles size={18} aria-hidden />
        Assistente de trabalho
      </div>
      <button className="link" onClick={a.openPage}>
        Conversas
      </button>
    </header>
  );
}

const modeLabel = { work: "Trabalho", general: "Geral" };

export function AssistantPage({ a }: { a: Assistant }) {
  const [confirming, setConfirming] = useState<number | null>(null);
  const [rule, setRule] = useState("");
  const chat = a[a.view];
  async function submitRule(e: FormEvent) {
    e.preventDefault();
    if (await a.addRule(rule.trim())) setRule("");
  }
  return (
    <div className="assistant-page">
      <aside className="panel conversations" aria-label="Conversas">
        <div className="panel-head">
          <h2>Conversas</h2>
        </div>
        <div className="new-chat">
          <button
            className="primary sm"
            disabled={a.general.busy}
            onClick={() => a.startNew("general")}
          >
            <Plus size={16} />
            Nova conversa
          </button>
          <button
            className="sm"
            disabled={a.work.busy}
            onClick={() => a.startNew("work")}
          >
            <Briefcase size={16} />
            Sobre meu trabalho
          </button>
        </div>
        <div className="conversation-list">
          {a.conversations.length === 0 && (
            <p className="hint">
              {a.connected
                ? "Suas conversas aparecem aqui depois da primeira pergunta."
                : "Na prévia do navegador as conversas não são salvas."}
            </p>
          )}
          {a.conversations.map((item) => {
            const Icon = item.mode === "work" ? Briefcase : MessageSquare;
            return confirming === item.id ? (
              <div className="conversation confirm" key={item.id}>
                <span>
                  Excluir esta conversa? As preferências aprendidas serão
                  mantidas.
                </span>
                <button
                  className="danger sm"
                  onClick={() => {
                    setConfirming(null);
                    void a.remove(item);
                  }}
                >
                  Excluir
                </button>
                <button className="sm" onClick={() => setConfirming(null)}>
                  Cancelar
                </button>
              </div>
            ) : (
              <div
                className={`conversation ${chat.conversationId === item.id ? "current" : ""}`}
                key={item.id}
              >
                <button
                  className="conversation-open"
                  disabled={a[item.mode].busy}
                  aria-current={
                    chat.conversationId === item.id ? "true" : undefined
                  }
                  onClick={() => void a.open(item)}
                >
                  <Icon size={16} aria-hidden />
                  <span>
                    <strong>{item.title}</strong>
                    <small>
                      {modeLabel[item.mode]} · {timeLabel(item.updated_at)}
                    </small>
                  </span>
                </button>
                <button
                  className="icon sm ghost"
                  aria-label={`Excluir conversa: ${item.title}`}
                  title="Excluir conversa"
                  disabled={a[item.mode].busy}
                  onClick={() => setConfirming(item.id)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })}
        </div>
        <div className="rules">
          <h3>Regras aprendidas</h3>
          <p className="hint">
            Quando você pede que o assistente passe a agir de certo modo, ele
            guarda a preferência aqui para as próximas conversas. As regras
            orientam as respostas, sem criar automações no sistema. Apague as
            que não quiser.
          </p>
          {a.rules.map((item) => (
            <div className="rule" key={item.id}>
              <span>
                {item.text}
                <small>
                  {item.source === "assistente"
                    ? "Criada pelo assistente"
                    : "Criada por você"}
                </small>
              </span>
              <button
                className="icon sm ghost"
                aria-label={`Apagar regra: ${item.text}`}
                title="Apagar regra"
                onClick={() => void a.removeRule(item)}
              >
                <X size={16} />
              </button>
            </div>
          ))}
          <form className="rule-form" onSubmit={(e) => void submitRule(e)}>
            <input
              aria-label="Nova regra"
              placeholder="Ex.: responder sempre em tópicos"
              minLength={8}
              maxLength={200}
              value={rule}
              disabled={!a.connected}
              onChange={(e) => setRule(e.target.value)}
            />
            <button className="sm" disabled={!a.connected || !rule.trim()}>
              Adicionar
            </button>
          </form>
        </div>
      </aside>
      <section className="panel full-chat">
        <div className="panel-head">
          <h2>
            {a.view === "work" ? "Assistente de trabalho" : "Conversa geral"}
          </h2>
          <span className="badge">
            {a.view === "work"
              ? "Usa os dados do Monitor"
              : "Sem contexto comercial automático"}
          </span>
        </div>
        <Chat chat={chat} />
      </section>
    </div>
  );
}
