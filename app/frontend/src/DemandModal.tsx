import { useEffect, useRef, useState } from "react";
import { ArrowRight, CircleAlert, X } from "lucide-react";
import { Demand, stages } from "./api";
import { HistoryEvent, isClosed, newDemand } from "./store";
import { Callout, dateLabel, frontLabel } from "./ui";

export function DemandModal({
  value,
  saving,
  error,
  onClose,
  onSave,
}: {
  value: Partial<Demand>;
  saving: boolean;
  error?: string;
  onClose: () => void;
  onSave: (d: Partial<Demand>) => void;
}) {
  const [form, setForm] = useState({ ...newDemand(), ...value });
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  const field = (key: keyof Demand, next: string | number | null) =>
    setForm((old) => ({ ...old, [key]: next }));
  const followUp = form.stage === "acompanhar";
  return (
    <dialog ref={ref} className="modal" onCancel={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(form);
        }}
      >
        <header>
          <div>
            <span className="eyebrow">
              {form.origin_ref ? "A partir de um e-mail" : "Próximo passo"}
            </span>
            <h2>{value.id ? "Editar demanda" : "Nova demanda"}</h2>
          </div>
          <button
            type="button"
            className="icon ghost"
            onClick={onClose}
            aria-label="Fechar formulário"
          >
            <X size={20} />
          </button>
        </header>
        {error && (
          <Callout icon={CircleAlert} tone="error" role="alert">
            {error}
          </Callout>
        )}
        <label className="field">
          Título
          <input
            autoFocus
            required
            maxLength={200}
            value={form.title}
            onChange={(e) => field("title", e.target.value)}
            placeholder="O que precisa ser feito?"
          />
        </label>
        <div className="form-grid">
          <label className="field">
            Frente
            <select
              aria-label="Frente"
              value={form.front_id}
              onChange={(e) => field("front_id", Number(e.target.value))}
            >
              {[1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>
                  {frontLabel(n)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Prioridade
            <select
              aria-label="Prioridade"
              value={form.priority}
              onChange={(e) => field("priority", e.target.value)}
            >
              <option value="normal">Normal</option>
              <option value="alta">Alta</option>
            </select>
          </label>
          <label className="field">
            Etapa
            <select
              aria-label="Etapa"
              value={form.stage}
              onChange={(e) => field("stage", e.target.value)}
            >
              {Object.entries(stages).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Prazo
            <input
              type="date"
              value={form.due || ""}
              onChange={(e) => field("due", e.target.value || null)}
            />
          </label>
          <label className="field">
            Contato
            <input
              value={form.contact}
              onChange={(e) => field("contact", e.target.value)}
              maxLength={200}
            />
          </label>
          <label className="field">
            <span>
              Data de retorno {followUp && <em>· obrigatória nesta etapa</em>}
            </span>
            <input
              type="date"
              required={followUp}
              value={form.return_date || ""}
              onChange={(e) => field("return_date", e.target.value || null)}
            />
          </label>
        </div>
        <label className="field">
          Próxima ação
          <input
            value={form.next_action}
            onChange={(e) => field("next_action", e.target.value)}
            maxLength={2000}
          />
        </label>
        <label className="field">
          Resumo
          <textarea
            value={form.summary}
            onChange={(e) => field("summary", e.target.value)}
            maxLength={6000}
          />
        </label>
        <footer>
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="primary" disabled={saving}>
            {saving ? "Salvando…" : "Salvar demanda"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}

export function DemandSheet({
  demand,
  history,
  persistent,
  onClose,
  onEdit,
  onAdvance,
  onRemove,
  onRemind,
}: {
  demand: Demand;
  history: HistoryEvent[];
  persistent: boolean;
  onClose: () => void;
  onEdit: () => void;
  onAdvance: () => void;
  onRemove: () => void;
  onRemind: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    const close = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);
  const facts: [string, string][] = [
    ["Contato", demand.contact || "Não informado"],
    ["Prazo", dateLabel(demand.due)],
    ["Data de retorno", dateLabel(demand.return_date)],
    ["Próxima ação", demand.next_action || "Ainda não definida"],
  ];
  return (
    <div className="overlay" onClick={onClose}>
      <section
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Detalhes da demanda"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <span className="eyebrow">
              {frontLabel(demand.front_id)} ·{" "}
              {demand.channel === "manual" ? "criada por você" : demand.channel}
            </span>
            <h2>{demand.title}</h2>
          </div>
          <button
            className="icon ghost"
            aria-label="Fechar detalhes"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        <div className="button-row">
          <span className="tag">
            {stages[demand.stage as keyof typeof stages]}
          </span>
          {demand.priority === "alta" && (
            <span className="tag priority">Prioridade alta</span>
          )}
        </div>
        <dl className="facts">
          {facts.map(([label, text]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{text}</dd>
            </div>
          ))}
          <div className="wide">
            <dt>Resumo</dt>
            <dd>{demand.summary || "Sem resumo"}</dd>
          </div>
        </dl>
        <div className="button-row">
          <button className="primary" onClick={onEdit}>
            Editar demanda
          </button>
          <button disabled={isClosed(demand)} onClick={onAdvance}>
            Próxima etapa
            <ArrowRight size={16} />
          </button>
          <button disabled={isClosed(demand)} onClick={onRemind}>Criar lembrete</button>
        </div>
        <div className="history">
          <h3>Histórico</h3>
          {history.length ? (
            history.map((event) => (
              <p key={event.id}>
                {event.description}
                <small>
                  {new Date(event.created_at).toLocaleString("pt-BR")}
                </small>
              </p>
            ))
          ) : (
            <p className="muted">
              {persistent
                ? "Nenhum evento registrado."
                : "O histórico fica disponível no aplicativo desktop."}
            </p>
          )}
        </div>
        <hr />
        {confirming ? (
          <div className="button-row">
            <button className="danger" onClick={onRemove}>
              Confirmar exclusão
            </button>
            <button className="ghost" onClick={() => setConfirming(false)}>
              Cancelar
            </button>
          </div>
        ) : (
          <div className="button-row">
            <button
              className="ghost danger"
              onClick={() => setConfirming(true)}
            >
              Excluir demanda
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
