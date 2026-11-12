import { useEffect, useRef, useState } from "react";
import { Bell, Check, Clock, Plus } from "lucide-react";
import { api } from "../api";
import type { Monitor } from "../store";
import { Callout, Empty, Panel } from "../ui";

export type Reminder = {
  id: number;
  text: string;
  when: string;
  demand_id: number | null;
  status: string;
};
export type Notice = {
  id: number;
  title: string;
  body: string;
  read: boolean;
  kind: string;
  created_at: string;
  demand_id: number | null;
  desktop_status: string;
};
type Config = {
  summary_enabled: boolean;
  summary_time: string;
  timezone: string;
  notifications_enabled: boolean;
  notification_details: boolean;
  auto_email_reminders: boolean;
};
type Summary = {
  date: string;
  body: string;
  demands: { id: number; title: string; front_id: number }[];
};
const defaults: Config = {
  summary_enabled: true,
  summary_time: "07:30",
  timezone: "America/Sao_Paulo",
  notifications_enabled: true,
  notification_details: false,
  auto_email_reminders: false,
};
const localInput = (value: Date) => {
  const d = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return d.toISOString().slice(0, 16);
};
const label = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });

export function Reminders({ m }: { m: Monitor }) {
  const [items, setItems] = useState<Reminder[]>([]),
    [notices, setNotices] = useState<Notice[]>([]),
    [config, setConfig] = useState<Config>(defaults),
    [summary, setSummary] = useState<Summary | null>(null);
  const [text, setText] = useState(
      m.reminderTarget
        ? `Lembrar: ${m.demands.find((d) => d.id === m.reminderTarget)?.title || "Retornar à demanda"}`.slice(
            0,
            300,
          )
        : "",
    ),
    [when, setWhen] = useState(localInput(new Date(Date.now() + 3600000))),
    [demand, setDemand] = useState(
      m.reminderTarget ? String(m.reminderTarget) : "",
    ),
    [editing, setEditing] = useState<number | null>(null),
    [working, setWorking] = useState(false),
    [showHistory, setShowHistory] = useState(false);
  const configured = useRef(false);
  useEffect(() => {
    m.setReminderTarget(null);
  }, []);
  async function refresh() {
    if (!m.connected) return;
    try {
      const [r, n, c, s] = await Promise.all([
        api<Reminder[]>("/reminders"),
        api<Notice[]>("/notifications"),
        api<Config>("/agenda/settings"),
        api<Summary>("/agenda/summary"),
      ]);
      setItems(r);
      setNotices(n);
      if (!configured.current) {
        setConfig(c);
        configured.current = true;
      }
      setSummary(s);
    } catch (e) {
      m.fail(e);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 15000);
    return () => clearInterval(timer);
  }, [m.connected]);
  async function action(work: () => Promise<unknown>) {
    setWorking(true);
    try {
      await work();
      await refresh();
      m.setNotice("Agenda atualizada.");
    } catch (e) {
      m.fail(e);
    } finally {
      setWorking(false);
    }
  }
  async function submit() {
    await action(async () => {
      const payload = {
        text,
        when: new Date(when).toISOString(),
        demand_id: demand ? Number(demand) : null,
      };
      if (m.connected)
        await api(
          editing ? `/reminders/${editing}` : "/reminders",
          editing ? "PUT" : "POST",
          payload,
        );
      else
        setItems((old) =>
          editing
            ? old.map((r) =>
                r.id === editing ? { ...r, ...payload, status: "pendente" } : r,
              )
            : [...old, { ...payload, id: Date.now(), status: "pendente" }],
        );
      setEditing(null);
      setText("");
      setDemand("");
    });
  }
  const active = items.filter((r) =>
    ["pendente", "disparado"].includes(r.status),
  );
  function edit(r: Reminder, delay = false) {
    setEditing(r.id);
    setText(r.text);
    setDemand(r.demand_id ? String(r.demand_id) : "");
    setWhen(
      localInput(delay ? new Date(Date.now() + 15 * 60000) : new Date(r.when)),
    );
    document.getElementById("reminder-text")?.focus();
  }
  async function resolve(r: Reminder, type: "complete" | "cancel") {
    await action(async () => {
      if (m.connected) await api(`/reminders/${r.id}/${type}`, "POST");
      else
        setItems((old) =>
          old.map((x) =>
            x.id === r.id
              ? {
                  ...x,
                  status: type === "complete" ? "concluido" : "cancelado",
                }
              : x,
          ),
        );
    });
  }
  const visible = (showHistory ? items : active).filter((r) => {
    const d = m.demands.find((d) => d.id === r.demand_id);
    return !m.front || d?.front_id === m.front;
  });
  return (
    <>
      <Callout>
        Os horários abaixo usam o fuso do computador. Com o Monitor na bandeja,
        os avisos continuam. Se o PC estiver desligado, os lembretes atrasados
        aparecem ao abrir novamente.
      </Callout>
      {!m.connected && (
        <Callout>
          Na demonstração, os lembretes ficam apenas nesta tela; nenhum aviso do
          Windows é enviado.
        </Callout>
      )}
      <div className="grid-2">
        <Panel title={editing ? "Reagendar lembrete" : "Novo lembrete"}>
          <form
            className="panel-body agenda-form"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <label>
              O que lembrar?
              <input
                id="reminder-text"
                required
                maxLength={300}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Retornar ao cliente sobre a proposta"
              />
            </label>
            <label>
              Data e hora
              <input
                type="datetime-local"
                required
                value={when}
                onChange={(e) => setWhen(e.target.value)}
              />
            </label>
            <label>
              Demanda relacionada
              <select
                aria-label="Demanda relacionada"
                value={demand}
                onChange={(e) => setDemand(e.target.value)}
              >
                <option value="">Sem vínculo</option>
                {m.demands
                  .filter((d) => !["ganho", "perdido"].includes(d.stage))
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title}
                    </option>
                  ))}
              </select>
            </label>
            <div className="button-row">
              <button className="primary" disabled={working || !text.trim()}>
                <Plus size={18} />
                {editing ? "Salvar agendamento" : "Criar lembrete"}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditing(null);
                    setText("");
                    setDemand("");
                  }}
                >
                  Cancelar edição
                </button>
              )}
            </div>
          </form>
        </Panel>
        <Panel title="Resumo de hoje">
          <div className="panel-body agenda-form">
            <p>
              {summary?.body ||
                "O resumo reúne demandas com prazo, lembretes e e-mails que precisam de ação."}
            </p>
            {summary?.demands.map((d) => (
              <button
                key={d.id}
                className="link"
                onClick={() => {
                  const item = m.demands.find((x) => x.id === d.id);
                  if (item) m.setDetail(item);
                }}
              >
                {d.title}
              </button>
            ))}
            <small>
              Atualiza sem depender do Ollama. O aviso diário segue o horário
              configurado abaixo.
            </small>
          </div>
        </Panel>
      </div>
      <Panel
        title="Sua agenda"
        action={
          <button
            className="ghost sm"
            onClick={() => setShowHistory(!showHistory)}
          >
            {showHistory ? "Mostrar pendentes" : "Ver histórico"}
          </button>
        }
      >
        {visible.length ? (
          visible.map((r) => (
            <div className="row agenda-row" key={r.id}>
              <Clock size={18} aria-hidden />
              <span className="row-body">
                <strong>{r.text}</strong>
                <small>
                  {label(r.when)} ·{" "}
                  {r.status === "disparado" ? "Hora de agir" : r.status}
                </small>
              </span>
              {["pendente", "disparado"].includes(r.status) && (
                <div className="button-row">
                  <button
                    className="sm"
                    disabled={working}
                    onClick={() => void resolve(r, "complete")}
                  >
                    <Check size={16} />
                    Concluir
                  </button>
                  <button
                    className="sm"
                    disabled={working}
                    onClick={() => edit(r, true)}
                  >
                    Adiar 15 min
                  </button>
                  <button
                    className="ghost sm"
                    disabled={working}
                    onClick={() => void resolve(r, "cancel")}
                  >
                    Cancelar
                  </button>
                </div>
              )}
            </div>
          ))
        ) : (
          <Empty
            icon={Bell}
            text="Nenhum lembrete neste filtro. Crie um agendamento para acompanhar seu próximo passo."
          />
        )}
      </Panel>
      <Panel title="Central de avisos">
        {notices.length ? (
          notices.map((n) => (
            <div className="row agenda-row" key={n.id}>
              <Bell size={18} aria-hidden />
              <span className="row-body">
                <strong>
                  {n.title}
                  {!n.read && " · Novo"}
                </strong>
                <small>
                  {label(n.created_at)} ·{" "}
                  {n.desktop_status === "enviada"
                    ? "Encaminhado ao Windows"
                    : "Disponível no Monitor"}
                </small>
                <p>{n.body}</p>
              </span>
              {!n.read && (
                <button
                  className="sm"
                  onClick={() =>
                    void action(() =>
                      api(`/notifications/${n.id}/read`, "POST"),
                    )
                  }
                >
                  Marcar como lido
                </button>
              )}
            </div>
          ))
        ) : (
          <Empty
            icon={Bell}
            text="Os lembretes e resumos aparecerão aqui, mesmo quando os avisos do Windows estiverem desativados."
          />
        )}
      </Panel>
      <Panel title="Preferências de avisos">
        <form
          className="panel-body agenda-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action(() => api("/agenda/settings", "PUT", config));
          }}
        >
          <label className="check">
            <input
              type="checkbox"
              checked={config.summary_enabled}
              onChange={(e) =>
                setConfig({ ...config, summary_enabled: e.target.checked })
              }
            />
            Resumo em dias úteis
          </label>
          <div className="form-grid">
            <label>
              Horário do resumo
              <input
                type="time"
                required
                value={config.summary_time}
                onChange={(e) =>
                  setConfig({ ...config, summary_time: e.target.value })
                }
              />
            </label>
            <label>
              Fuso do resumo
              <select
                aria-label="Fuso do resumo"
                value={config.timezone}
                onChange={(e) =>
                  setConfig({ ...config, timezone: e.target.value })
                }
              >
                {Array.from(
                  new Set([
                    config.timezone,
                    "America/Sao_Paulo",
                    "America/Manaus",
                    "America/Rio_Branco",
                    "Europe/Lisbon",
                    "UTC",
                  ]),
                ).map((z) => (
                  <option key={z}>{z}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={config.notifications_enabled}
              onChange={(e) =>
                setConfig({
                  ...config,
                  notifications_enabled: e.target.checked,
                })
              }
            />
            Exibir avisos do Windows
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={config.notification_details}
              onChange={(e) =>
                setConfig({ ...config, notification_details: e.target.checked })
              }
            />
            Mostrar detalhes nos avisos do Windows
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={config.auto_email_reminders}
              onChange={(e) =>
                setConfig({ ...config, auto_email_reminders: e.target.checked })
              }
            />
            Criar lembretes de prazos explícitos confirmados pela IA
          </label>
          <small>
            Ao ativar a criação automática, prazos com confiança de pelo menos
            90% e trecho de origem geram lembretes às 9h no fuso configurado.
            Essa confiança é informada pelo modelo, não uma garantia de acerto.
            Revise os agendamentos.
          </small>
          <button className="primary" disabled={working || !m.connected}>
            Salvar preferências
          </button>
        </form>
      </Panel>
    </>
  );
}
