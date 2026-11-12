import { useEffect, useState } from "react";
import {
  Activity,
  CircleAlert,
  Folder,
  Globe,
  LayoutDashboard,
  Mail,
  MessageSquare,
  Plus,
  Search,
  Settings,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";
import { api, stages } from "./api";
import { DemandModal, DemandSheet } from "./DemandModal";
import { Demands } from "./pages/Demands";
import { Emails } from "./pages/Emails";
import { AssistantHeader, Chat, Files, Sites, Social } from "./pages/Other";
import { Overview } from "./pages/Overview";
import { SettingsPage } from "./pages/SettingsPage";
import { HistoryEvent, isClosed, newDemand, Page, useMonitor } from "./store";
import { Callout } from "./ui";

export { DemandModal };

const nav: Record<Page, { icon: typeof Mail; title: string; lead: string }> = {
  "Visão geral": {
    icon: LayoutDashboard,
    title: "Tudo sob controle.",
    lead: "Menos ruído. Mais foco no que precisa de você.",
  },
  Demandas: {
    icon: Workflow,
    title: "Cada oportunidade, um próximo passo.",
    lead: "Arraste um cartão para mudar de etapa ou abra para ver os detalhes.",
  },
  "E-mails": {
    icon: Mail,
    title: "Sua caixa de entrada, organizada.",
    lead: "Todas as contas em um só lugar, em modo somente leitura.",
  },
  Sites: {
    icon: Globe,
    title: "Sua presença sempre à vista.",
    lead: "Disponibilidade, SSL e formulários das suas frentes.",
  },
  "Redes sociais": {
    icon: Activity,
    title: "Acompanhe suas conexões.",
    lead: "Seguidores, engajamento e mensagens pendentes.",
  },
  Arquivos: {
    icon: Folder,
    title: "Tudo no lugar certo.",
    lead: "Backups, exportações e documentos na sua pasta da nuvem.",
  },
  Assistente: {
    icon: MessageSquare,
    title: "Pense junto com seu assistente.",
    lead: "Perguntas sobre seus dados, respondidas neste computador.",
  },
  Configurações: {
    icon: Settings,
    title: "Do seu jeito.",
    lead: "Pasta de arquivos, contas, regras e IA local.",
  },
};
const withFronts: Page[] = [
  "Visão geral",
  "Demandas",
  "E-mails",
  "Sites",
  "Redes sociais",
  "Arquivos",
];
const withSearch: Page[] = ["Visão geral", "Demandas", "Arquivos"];

export default function App() {
  const m = useMonitor();
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const { detail, connected } = m;
  useEffect(() => {
    setHistory([]);
    if (!detail || !connected) return;
    api<HistoryEvent[]>(`/demands/${detail.id}/events`)
      .then(setHistory)
      .catch(() => {});
  }, [detail, connected]);

  const ready = m.connected || m.preview;
  const overview = m.page === "Visão geral" && ready;
  const current = nav[m.page];
  return (
    <div className={`app ${overview ? "with-assistant" : ""}`}>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            m.setPage("Visão geral");
          }}
        >
          <span className="brand-mark" aria-hidden />
          MONITOR
        </a>
        <span className="eyebrow">Espaço de trabalho</span>
        <nav aria-label="Seções">
          {(Object.keys(nav) as Page[]).map((label) => {
            const Icon = nav[label].icon;
            const count =
              label === "Demandas"
                ? m.demands.filter((d) => !isClosed(d)).length
                : label === "E-mails"
                  ? m.suggested.length
                  : 0;
            return (
              <button
                key={label}
                aria-label={label}
                aria-current={m.page === label ? "page" : undefined}
                title={label}
                className={m.page === label ? "active" : ""}
                onClick={() => m.setPage(label)}
              >
                <Icon size={18} aria-hidden />
                <span>{label}</span>
                {count > 0 && <span className="nav-count">{count}</span>}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div>
            <span className={`dot ${m.connected ? "cyan" : "off"}`} />
            {m.connected ? "Backend local conectado" : "Prévia da interface"}
          </div>
          <div>
            <span className="avatar">M</span>
            <span>
              <strong>Marcos</strong>
              Seu espaço pessoal
            </span>
          </div>
        </div>
      </aside>
      <main className="main">
        <div className="content">
          <header className="page-header">
            <div>
              <span className="eyebrow">
                {new Date().toLocaleDateString("pt-BR", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                })}
              </span>
              <h1>{current.title}</h1>
              <p>{current.lead}</p>
            </div>
            <div className="page-actions">
              {m.preview && (
                <span className="badge">Demonstração · dados fictícios</span>
              )}
              <button
                className="primary"
                onClick={() =>
                  m.setEditing({ ...newDemand(), front_id: m.front || 1 })
                }
                disabled={!ready}
              >
                <Plus size={18} />
                Nova demanda
              </button>
            </div>
          </header>
          {m.error && !m.editing && (
            <Callout
              icon={CircleAlert}
              tone="error"
              role="alert"
              action={
                <button
                  className="icon sm ghost"
                  onClick={() => m.setError("")}
                  aria-label="Fechar erro"
                >
                  <X size={16} />
                </button>
              }
            >
              {m.error}
            </Callout>
          )}
          {!ready ? (
            <section className="panel">
              <div className="empty">
                <Sparkles size={28} aria-hidden />
                <h2>
                  {m.busy ? "Iniciando sua central…" : "Bem-vindo ao Monitor"}
                </h2>
                <p>
                  O aplicativo desktop guarda suas demandas e e-mails neste
                  computador. Você também pode explorar uma demonstração com
                  dados fictícios, sem salvar nada.
                </p>
                <div className="button-row">
                  <button
                    className="primary"
                    onClick={() => void m.load()}
                    disabled={m.busy}
                  >
                    Tentar conectar
                  </button>
                  <button onClick={m.startDemo}>Explorar demonstração</button>
                </div>
              </div>
            </section>
          ) : (
            <>
              {withFronts.includes(m.page) && (
                <div className="toolbar">
                  <div
                    className="segmented"
                    role="group"
                    aria-label="Filtrar por frente"
                  >
                    {[0, 1, 2, 3, 4].map((n) => (
                      <button
                        key={n}
                        aria-pressed={m.front === n}
                        onClick={() => m.setFront(n)}
                      >
                        {n === 0 ? "Todas as frentes" : `Frente 0${n}`}
                      </button>
                    ))}
                  </div>
                  {withSearch.includes(m.page) && (
                    <label className="search">
                      <Search size={16} aria-hidden />
                      <input
                        aria-label="Buscar"
                        placeholder={
                          m.page === "Arquivos"
                            ? "Buscar arquivo…"
                            : "Buscar demanda…"
                        }
                        value={m.query}
                        onChange={(e) => m.setQuery(e.target.value)}
                      />
                    </label>
                  )}
                </div>
              )}
              {m.page === "Visão geral" && <Overview m={m} />}
              {m.page === "Demandas" && <Demands m={m} />}
              {m.page === "E-mails" && <Emails m={m} />}
              {m.page === "Sites" && <Sites m={m} />}
              {m.page === "Redes sociais" && <Social m={m} />}
              {m.page === "Arquivos" && <Files m={m} />}
              {m.page === "Assistente" && (
                <section className="panel full-chat">
                  <Chat />
                </section>
              )}
              {m.page === "Configurações" && <SettingsPage m={m} />}
            </>
          )}
        </div>
      </main>
      {overview && (
        <aside className="assistant" aria-label="Assistente">
          <AssistantHeader />
          <Chat />
        </aside>
      )}
      {m.notice && (
        <div role="status" className="toast">
          <span className="dot" />
          {m.notice}
        </div>
      )}
      {m.editing && (
        <DemandModal
          value={m.editing}
          saving={m.saving}
          error={m.error}
          onClose={() => {
            m.setEditing(null);
            m.setError("");
          }}
          onSave={(value) => void m.saveDemand(value)}
        />
      )}
      {m.detail && (
        <DemandSheet
          demand={m.detail}
          history={history}
          persistent={m.connected}
          onClose={() => m.setDetail(null)}
          onEdit={() => {
            m.setEditing(m.detail);
            m.setDetail(null);
          }}
          onAdvance={() => {
            const order = Object.keys(stages);
            const next = order[order.indexOf(m.detail!.stage) + 1];
            if (next) m.moveDemand(m.detail!, next);
          }}
          onRemove={() => void m.removeDemand(m.detail!)}
        />
      )}
    </div>
  );
}
