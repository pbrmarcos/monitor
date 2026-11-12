import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Folder,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { chatStream } from "../api";
import { files } from "../demo";
import type { Monitor } from "../store";
import { Callout, Empty, frontLabel, Panel, sample, soon } from "../ui";

export function Files({ m }: { m: Monitor }) {
  const [category, setCategory] = useState("Todas");
  const folder = m.storage?.files_dir;
  const list = files.filter(
    (f) =>
      (!m.front || f.front === m.front) &&
      (category === "Todas" || f.category === category) &&
      f.name.toLowerCase().includes(m.query.toLowerCase()),
  );
  return (
    <>
      <Panel
        title="Pasta do Monitor"
        action={
          <button
            className="ghost sm"
            onClick={() => m.setPage("Configurações")}
          >
            {folder ? "Alterar" : "Escolher pasta"}
            <ArrowRight size={16} />
          </button>
        }
      >
        <div className="panel-body">
          {folder ? (
            <>
              <p className="path">{folder}</p>
              <p>
                {m.storage?.last_backup
                  ? `Último backup do banco: ${new Date(m.storage.last_backup + "T12:00:00").toLocaleDateString("pt-BR")}.`
                  : "Nenhum backup gravado ainda."}{" "}
                {m.storage?.in_onedrive
                  ? "Pasta sincronizada pelo OneDrive."
                  : "Esta pasta não está no OneDrive."}
              </p>
            </>
          ) : (
            <p>
              Escolha a pasta onde o Monitor guarda backups, exportações e os
              arquivos que organizar. Uma pasta do OneDrive mantém tudo na
              nuvem.
            </p>
          )}
        </div>
      </Panel>
      <Panel title="Catálogo" action={m.preview ? sample : soon}>
        {m.preview ? (
          <>
            <div className="toolbar" style={{ padding: "0 20px 12px" }}>
              <p>Arquivos fictícios</p>
              <select
                aria-label="Categoria do arquivo"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {["Todas", "Proposta", "Briefing", "Material"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Arquivo</th>
                    <th>Frente</th>
                    <th>Categoria</th>
                    <th>Tamanho</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((f) => (
                    <tr key={f.name}>
                      <td>
                        <FileText size={16} aria-hidden />
                        {f.name}
                      </td>
                      <td>{frontLabel(f.front)}</td>
                      <td>{f.category}</td>
                      <td>{f.size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty
            icon={Folder}
            text="A indexação da pasta, a busca e a classificação dos arquivos chegam em uma próxima versão."
          />
        )}
      </Panel>
    </>
  );
}

const OFFLINE =
  "Na prévia do navegador o assistente não fala com o modelo. Abra o aplicativo desktop para conversar.";

type ChatMessage = { role: "user" | "assistant"; text: string; error?: boolean };

/** Conversa única, compartilhada entre o painel da visão geral e a tela do assistente. */
export function useChat(m: Monitor) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const ready = m.connected && !!m.ollama?.models.includes(m.settings.model);
  const reply = (change: (last: ChatMessage) => ChatMessage) =>
    setMessages((old) => [...old.slice(0, -1), change(old[old.length - 1])]);
  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history = [
      ...messages.filter((item) => !item.error && item.text),
      { role: "user" as const, text: question },
    ];
    setMessages((old) => [
      ...old,
      { role: "user", text: question },
      { role: "assistant", text: m.connected ? "" : OFFLINE },
    ]);
    if (!m.connected) return;
    setBusy(true);
    try {
      await chatStream(
        history.map((item) => ({ role: item.role, content: item.text })),
        (delta) => reply((last) => ({ ...last, text: last.text + delta })),
      );
    } catch (e) {
      reply(() => ({
        role: "assistant",
        text: (e as Error).message,
        error: true,
      }));
    } finally {
      setBusy(false);
    }
  }
  return {
    messages,
    busy,
    ready,
    ask,
    clear: () => setMessages([]),
    openSettings: () => m.setPage("Configurações"),
    preview: !m.connected,
    available: !!m.ollama?.available,
    model: m.settings.model,
  };
}

export function Chat({ chat }: { chat: ReturnType<typeof useChat> }) {
  const [question, setQuestion] = useState("");
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => {
    log.current?.scrollTo?.({ top: log.current.scrollHeight });
  }, [chat.messages]);
  function send(text: string) {
    void chat.ask(text);
    setQuestion("");
  }
  return (
    <div className="chat">
      {chat.messages.length === 0 && (
        <div className="chat-intro">
          <h3>Um pouco mais de clareza.</h3>
          <p>
            Pergunte sobre suas demandas, prazos, e-mails e lembretes. A
            resposta sai do modelo instalado neste computador e cita de onde
            veio cada informação.
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
            : "O Ollama não respondeu. Abra o Ollama e verifique de novo em Configurações."}
        </Callout>
      )}
      <div className="chat-log" aria-live="polite" ref={log}>
        {chat.messages.map((message, i) => (
          <div
            key={i}
            className={`message message-${message.role} ${message.error ? "error" : ""}`}
          >
            {message.text || "Pensando…"}
          </div>
        ))}
      </div>
      <div className="prompts">
        {["O que priorizar hoje?", "Resumir meus e-mails"].map((prompt) => (
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
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(question);
        }}
      >
        <textarea
          aria-label="Mensagem para o assistente"
          placeholder="Converse com seu assistente…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(question);
            }
          }}
        />
        <button
          className="icon sm primary"
          aria-label="Enviar mensagem"
          disabled={chat.busy || !question.trim()}
        >
          <ArrowRight size={18} />
        </button>
      </form>
      <div className="chat-foot">
        <small>IA local · confira as respostas antes de agir</small>
        {chat.messages.length > 0 && (
          <button className="link" disabled={chat.busy} onClick={chat.clear}>
            Limpar conversa
          </button>
        )}
      </div>
    </div>
  );
}

export function AssistantHeader() {
  return (
    <header>
      <div>
        <Sparkles size={18} aria-hidden />
        Assistente
      </div>
      <span className="badge ai">Local</span>
    </header>
  );
}
