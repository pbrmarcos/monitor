import { useEffect, useRef, useState } from "react";
import {
  X,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Trash2,
  Activity,
  Cpu,
  Layers,
} from "lucide-react";
import {
  api,
  Attachment,
  AssistantDiagnostics,
  AssistantRecord,
  AssistantSkill,
  InferenceMetrics,
} from "../api";

const number = (value: number) =>
  value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
const gib = (value: number) => `${number(value / 1024 ** 3)} GiB`;
const date = (value: string) =>
  new Date(
    /Z$|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z",
  ).toLocaleString("pt-BR");

export function ResponseMetrics({ value }: { value: InferenceMetrics }) {
  const fields: [string, number | null | undefined, string][] = [
    ["Tokens de entrada", value.input_tokens, ""],
    ["Tokens gerados", value.output_tokens, ""],
    ["Geração", value.generation_seconds, " s"],
    ["Leitura do contexto", value.prompt_seconds, " s"],
    ["Carga do modelo", value.load_seconds, " s"],
    ["Primeiro texto", value.first_token_seconds, " s"],
    ["Tempo total observado", value.wall_seconds, " s"],
  ];
  return (
    <details className="response-metrics">
      <summary>
        {value.tokens_per_second != null
          ? `${number(value.tokens_per_second)} tk/s`
          : "Métricas"}
        {value.output_tokens != null &&
          ` · ${number(value.output_tokens)} tokens`}
        {value.wall_seconds != null && ` · ${number(value.wall_seconds)} s`}
      </summary>
      <dl>
        {fields
          .filter(([, value]) => value != null)
          .map(([label, value, unit]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>
                {number(value!)}
                {unit}
              </dd>
            </div>
          ))}
      </dl>
      <p>
        tk/s = tokens gerados ÷ tempo de geração informado pelo Ollama. Não
        inclui carga nem leitura do contexto.
      </p>
    </details>
  );
}

export function ImageViewer({
  file,
  close,
}: {
  file: { id: number; name: string };
  close: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [image, setImage] = useState<(Attachment & { src: string }) | null>(
    null,
  );
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(100);
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    let cancelled = false;
    void api<Attachment & { src: string }>(
      `/assistant/attachments/${file.id}/preview`,
    )
      .then((value) => {
        if (!cancelled) setImage(value);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      });
    return () => {
      cancelled = true;
      node?.close();
    };
  }, [file.id]);
  return (
    <dialog
      ref={dialog}
      className="image-viewer"
      aria-label={`Visualizar ${file.name}`}
      onCancel={close}
    >
      <header>
        <div>
          <strong>{file.name}</strong>
          <small>
            Imagem armazenada neste computador
            {image ? ` · ${number(image.size / 1024)} KB` : ""}
          </small>
        </div>
        <button
          className="icon"
          aria-label="Fechar visualizador"
          onClick={close}
        >
          <X aria-hidden size={20} />
        </button>
      </header>
      <div className="image-viewer-toolbar">
        <button
          className="icon sm"
          aria-label="Diminuir imagem"
          disabled={zoom <= 50}
          onClick={() => setZoom((value) => Math.max(50, value - 25))}
        >
          <ZoomOut aria-hidden size={18} />
        </button>
        <span>{zoom}%</span>
        <button
          className="icon sm"
          aria-label="Ampliar imagem"
          disabled={zoom >= 300}
          onClick={() => setZoom((value) => Math.min(300, value + 25))}
        >
          <ZoomIn aria-hidden size={18} />
        </button>
        <button className="sm" onClick={() => setZoom(100)}>
          Ajustar à tela
        </button>
      </div>
      <div className="image-viewer-stage">
        {error ? (
          <p role="alert">{error}</p>
        ) : image ? (
          <img
            src={image.src}
            alt={file.name}
            style={{
              width: `${zoom}%`,
              maxHeight: zoom === 100 ? "65vh" : "none",
            }}
          />
        ) : (
          <p role="status">Carregando imagem…</p>
        )}
      </div>
    </dialog>
  );
}

const states: Record<string, string> = {
  running: "Em andamento",
  completed: "Concluído",
  error: "Falhou",
  interrupted: "Interrompido",
};
export function AssistantRecords({
  connected,
  openConversation,
}: {
  connected: boolean;
  openConversation: (id: number) => void;
}) {
  const [records, setRecords] = useState<AssistantRecord[]>([]);
  const [diagnostics, setDiagnostics] = useState<AssistantDiagnostics | null>(
    null,
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  async function refresh() {
    if (!connected) return;
    setBusy(true);
    setError("");
    try {
      const [logs, data] = await Promise.all([
        api<AssistantRecord[]>("/assistant/records"),
        api<AssistantDiagnostics>("/assistant/diagnostics"),
      ]);
      setRecords(logs);
      setDiagnostics(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void refresh();
  }, [connected]);
  const loaded = diagnostics?.loaded.find(
    (item) =>
      item.name === diagnostics.model ||
      item.name === diagnostics.model + ":latest",
  );
  return (
    <section className="assistant-tools panel">
      <div className="panel-head">
        <h2>
          <Activity aria-hidden size={18} /> Registros e dados da IA
        </h2>
        <button
          className="sm"
          disabled={!connected || busy}
          onClick={() => void refresh()}
        >
          <RefreshCw aria-hidden size={16} />
          {busy ? "Atualizando…" : "Atualizar"}
        </button>
      </div>
      <div className="panel-body">
        <p className="muted">
          Métricas locais, sem armazenar prompts, respostas ou imagens nos logs.
          Mantém os 200 registros mais recentes. As métricas das respostas
          permanecem no chat.
        </p>
        {!connected && (
          <p>Abra o aplicativo desktop para consultar os registros.</p>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="ai-diagnostic-grid">
          <article>
            <Cpu aria-hidden size={18} />
            <small>Modelo selecionado</small>
            <strong>{diagnostics?.model ?? "—"}</strong>
            <span>
              {diagnostics?.available
                ? loaded
                  ? "Carregado"
                  : "Aguardando carga"
                : "Ollama indisponível"}
            </span>
          </article>
          <article>
            <Layers aria-hidden size={18} />
            <small>Contexto e permanência</small>
            <strong>
              {diagnostics ? number(diagnostics.context) + " tokens" : "—"}
            </strong>
            <span>
              {diagnostics?.keep_alive ?? "—"} · até 2 skills por pergunta
            </span>
          </article>
          <article>
            <Cpu aria-hidden size={18} />
            <small>VRAM do modelo · Ollama</small>
            <strong>{loaded ? gib(loaded.size_vram) : "—"}</strong>
            <span>
              {loaded
                ? `Total alocado: ${gib(loaded.size)} · contexto carregado: ${number(loaded.context_length)}`
                : "GPU de 6 GB: mantemos o modelo escolhido"}
            </span>
          </article>
        </div>
        <div className="ai-last-activity">
          <small>Última atividade registrada</small>
          <strong>
            {records[0]?.detail || "Nenhuma atividade registrada ainda."}
          </strong>
          {records[0] && (
            <span>
              {date(records[0].created_at)} ·{" "}
              {states[records[0].status] ?? records[0].status}
            </span>
          )}
        </div>
        <div className="split">
          <h3>Histórico de atividades</h3>
          {confirm ? (
            <div className="button-row">
              <button
                className="danger sm"
                onClick={async () => {
                  try {
                    await api("/assistant/records", "DELETE");
                    setConfirm(false);
                    await refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Confirmar limpeza dos logs
              </button>
              <button className="sm" onClick={() => setConfirm(false)}>
                Cancelar
              </button>
            </div>
          ) : (
            <button
              className="sm"
              disabled={!connected || !records.length}
              onClick={() => setConfirm(true)}
            >
              <Trash2 aria-hidden size={15} />
              Limpar registros
            </button>
          )}
        </div>
        <div className="ai-record-list">
          {records.map((row) => (
            <article key={row.id} className="ai-record">
              <div className="split">
                <strong>{row.detail}</strong>
                <span
                  className={`badge ${row.status === "error" ? "warning" : ""}`}
                >
                  {states[row.status] ?? row.status}
                </span>
              </div>
              <small>
                {date(row.created_at)} · #{row.id} ·{" "}
                {row.kind === "action"
                  ? "Ferramenta local"
                  : row.kind === "attachment"
                    ? "Anexo"
                    : row.model}
              </small>
              {!!row.skills.length && (
                <p className="small muted">Skills: {row.skills.join(" · ")}</p>
              )}
              {!!Object.keys(row.metrics).length && (
                <ResponseMetrics value={row.metrics} />
              )}
              {row.conversation_id != null && (
                <button
                  className="link small"
                  onClick={() => openConversation(row.conversation_id!)}
                >
                  Abrir conversa
                </button>
              )}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function AssistantSkills({ connected }: { connected: boolean }) {
  const [skills, setSkills] = useState<AssistantSkill[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    keywords: "",
    instructions: "",
  });
  useEffect(() => {
    if (connected)
      void api<AssistantSkill[]>("/assistant/skills")
        .then(setSkills)
        .catch((e) => setError(e.message));
  }, [connected]);
  return (
    <section className="assistant-tools panel">
      <div className="panel-head">
        <h2>
          <Layers aria-hidden size={18} /> Skills do assistente
        </h2>
        <span className="badge">Sem outro modelo</span>
      </div>
      <div className="panel-body">
        <p>
          Skills orientam como responder a cada tarefa. O Monitor seleciona até
          duas por pergunta, sem treinar pesos, carregar outro modelo ou ampliar
          o contexto de 16 mil tokens. Elas não dão novas permissões ao
          assistente.
        </p>
        {!connected && (
          <p>Abra o aplicativo desktop para configurar as skills.</p>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="ai-skill-grid">
          {skills.map((skill) => (
            <article key={skill.id} className="ai-skill">
              <label className="check">
                <input
                  type="checkbox"
                  checked={skill.enabled}
                  disabled={busy || !connected}
                  onChange={async (e) => {
                    setBusy(true);
                    setError("");
                    try {
                      setSkills(
                        await api<AssistantSkill[]>(
                          `/assistant/skills/${skill.id}`,
                          "PUT",
                          { enabled: e.target.checked },
                        ),
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
                <strong>{skill.name}</strong>
              </label>
              <p>{skill.description}</p>
              <small>Gatilhos: {skill.keywords}</small>
              <details>
                <summary>Ver instruções</summary>
                <p>{skill.instructions}</p>
              </details>
              {!skill.builtin &&
                (deleting !== skill.id ? (
                  <button
                    className="link"
                    disabled={busy}
                    onClick={() => setDeleting(skill.id)}
                  >
                    Excluir skill
                  </button>
                ) : (
                  <div className="button-row">
                    <button
                      className="danger sm"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await api(`/assistant/skills/${skill.id}`, "DELETE");
                          setSkills((old) =>
                            old.filter((item) => item.id !== skill.id),
                          );
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Confirmar exclusão
                    </button>
                    <button className="sm" onClick={() => setDeleting(null)}>
                      Cancelar
                    </button>
                  </div>
                ))}
            </article>
          ))}
        </div>
        <h3>Adicionar skill</h3>
        <form
          className="form-grid"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const saved = await api<AssistantSkill>(
                "/assistant/skills",
                "POST",
                form,
              );
              setSkills((old) => [...old, saved]);
              setForm({
                name: "",
                description: "",
                keywords: "",
                instructions: "",
              });
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            Nome
            <input
              required
              minLength={3}
              maxLength={60}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label className="field">
            Palavras-chave separadas por vírgula
            <input
              required
              minLength={3}
              maxLength={160}
              placeholder="proposta, orçamento"
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
            />
          </label>
          <label className="field">
            Descrição
            <input
              maxLength={160}
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
          </label>
          <label className="field">
            Instruções
            <textarea
              required
              minLength={10}
              maxLength={600}
              rows={4}
              value={form.instructions}
              onChange={(e) =>
                setForm({ ...form, instructions: e.target.value })
              }
            />
          </label>
          <button className="primary" disabled={!connected || busy}>
            Adicionar skill
          </button>
        </form>
      </div>
    </section>
  );
}
