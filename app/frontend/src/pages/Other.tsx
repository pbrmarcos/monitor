import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Folder,
  Globe,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { files } from "../demo";
import { newDemand, type Monitor } from "../store";
import { Callout, Empty, frontLabel, Panel, sample, soon } from "../ui";
import { SocialTable } from "./Overview";

export function Sites({ m }: { m: Monitor }) {
  if (!m.preview)
    return (
      <Panel title="Monitoramento" action={soon}>
        <Empty
          icon={Globe}
          text="Disponibilidade, tempo de resposta, validade do SSL e teste dos formulários chegam em uma próxima versão."
        />
      </Panel>
    );
  return (
    <>
      <Callout>
        Dados de demonstração. Nenhum site real está sendo verificado.
      </Callout>
      <div className="grid-2">
        {[1, 2, 3, 4]
          .filter((n) => !m.front || m.front === n)
          .map((n) => (
            <Panel key={n} title={`frente0${n}.example`} action={sample}>
              <div className="panel-body">
                <div className="split">
                  <span>
                    <span className="dot" /> Online
                  </span>
                  <strong>99,98%</strong>
                </div>
                <div className="uptime" aria-hidden>
                  {Array.from({ length: 30 }, (_, i) => (
                    <span key={i} />
                  ))}
                </div>
                <dl className="facts">
                  <div>
                    <dt>Resposta</dt>
                    <dd>{180 + n * 17} ms</dd>
                  </div>
                  <div>
                    <dt>SSL</dt>
                    <dd>82 dias</dd>
                  </div>
                </dl>
              </div>
            </Panel>
          ))}
      </div>
    </>
  );
}

export function Social({ m }: { m: Monitor }) {
  return (
    <>
      {m.preview && (
        <Callout>
          Dados de demonstração. Nenhuma conta do Instagram ou WhatsApp está
          conectada.
        </Callout>
      )}
      <Panel title="Perfis" action={m.preview ? sample : soon}>
        <SocialTable m={m} />
      </Panel>
      {m.preview && (
        <Panel title="Mensagens sem resposta" action={sample}>
          <div className="row">
            <span className="row-icon">
              <MessageSquare size={18} aria-hidden />
            </span>
            <span className="row-body">
              <strong>Olá! Gostaria de saber mais sobre o serviço.</strong>
              <small>@contato_exemplo · {frontLabel(1)}</small>
            </span>
            <button
              className="sm"
              onClick={() =>
                m.setEditing({
                  ...newDemand(),
                  title: "Responder interesse no serviço",
                  channel: "instagram",
                })
              }
            >
              + Demanda
            </button>
          </div>
        </Panel>
      )}
    </>
  );
}

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

const REPLY =
  "O chat ainda não está conectado ao modelo. Por enquanto, consulte a fila de demandas e a caixa de e-mails no painel. Nenhuma mensagem foi enviada.";

export function Chat() {
  const [messages, setMessages] = useState<{ role: string; text: string }[]>(
    [],
  );
  const [question, setQuestion] = useState("");
  function ask(text: string) {
    if (!text.trim()) return;
    setMessages((old) => [
      ...old,
      { role: "user", text },
      { role: "assistant", text: REPLY },
    ]);
    setQuestion("");
  }
  return (
    <div className="chat">
      {messages.length === 0 && (
        <div className="chat-intro">
          {soon}
          <h3>Um pouco mais de clareza.</h3>
          <p>
            Em breve o assistente responderá sobre suas demandas, prazos e
            e-mails, sempre citando as fontes.
          </p>
        </div>
      )}
      <div className="chat-log" aria-live="polite">
        {messages.map((message, i) => (
          <div key={i} className={`message ${message.role}`}>
            {message.text}
          </div>
        ))}
      </div>
      <div className="prompts">
        {["O que priorizar hoje?", "Resumir meus e-mails"].map((prompt) => (
          <button key={prompt} onClick={() => ask(prompt)}>
            {prompt}
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <textarea
          aria-label="Mensagem para o assistente"
          placeholder="Converse com seu assistente…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="icon sm primary" aria-label="Enviar mensagem">
          <ArrowRight size={18} />
        </button>
      </form>
      <small>IA local · sugestões precisam de revisão</small>
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
