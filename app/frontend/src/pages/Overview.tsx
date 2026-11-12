import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  ChevronRight,
  CircleCheck,
  CircleDashed,
  Globe,
  Mail,
  MessageSquare,
  Plus,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { Demand, importanceLabels, stages } from "../api";
import { today } from "../demo";
import type { Monitor } from "../store";
import { fresh, siteStatus, useSites } from "./Sites";
import {
  dateLabel,
  Empty,
  frontLabel,
  Panel,
  sample,
  senderName,
  soon,
  Tabs,
} from "../ui";

type QueueTab = "Hoje" | "Todas" | "Sugestões da IA";

export function DemandRows({ items, m }: { items: Demand[]; m: Monitor }) {
  if (!items.length)
    return <Empty icon={CircleCheck} text="Tudo em dia por aqui." />;
  return (
    <div>
      {items.map((d) => (
        <button className="row" key={d.id} onClick={() => m.setDetail(d)}>
          <span className="row-body">
            <strong className="truncate">{d.title}</strong>
            <small>
              {frontLabel(d.front_id)} ·{" "}
              {d.channel === "manual" ? "Criada por você" : d.channel}
            </small>
          </span>
          <span
            className={`row-meta ${d.due && d.due < today() ? "overdue" : ""}`}
          >
            {dateLabel(d.due || d.return_date)}
          </span>
          <span className={`tag ${d.priority === "alta" ? "priority" : ""}`}>
            {d.priority === "alta"
              ? "Prioridade"
              : stages[d.stage as keyof typeof stages]}
          </span>
          <ChevronRight size={16} aria-hidden />
        </button>
      ))}
    </div>
  );
}

function FirstSteps({ m }: { m: Monitor }) {
  const model =
    !!m.ollama?.available && m.ollama.models.includes(m.settings.model);
  const steps = [
    {
      done: !!m.storage?.files_dir,
      title: "Pasta de arquivos",
      text: m.storage?.files_dir
        ? m.storage.files_dir
        : "Escolha onde ficam backups e arquivos, de preferência no OneDrive.",
      action: "Escolher pasta",
    },
    {
      done: m.accounts.length > 0,
      title: "Contas de e-mail",
      text: m.accounts.length
        ? `${m.accounts.length} conta(s) em leitura.`
        : "Conecte as caixas das suas frentes. O Monitor só lê, nunca altera.",
      action: "Conectar conta",
    },
    {
      done: model,
      title: "IA local",
      text: model
        ? "Ollama e modelo prontos."
        : m.ollama?.available
          ? "O modelo escolhido ainda não foi baixado."
          : "Ollama não detectado. Sem ele, as regras fazem a triagem.",
      action: "Configurar IA",
    },
  ];
  if (steps.every((step) => step.done)) return null;
  return (
    <Panel
      title="Primeiros passos"
      action={
        <span className="badge">
          {steps.filter((step) => step.done).length} de 3
        </span>
      }
    >
      <div className="steps">
        {steps.map((step) => (
          <div className={`step ${step.done ? "done" : ""}`} key={step.title}>
            {step.done ? <CircleCheck size={20} /> : <CircleDashed size={20} />}
            <h3>{step.title}</h3>
            <p className={step.done ? "truncate" : ""}>{step.text}</p>
            {!step.done && (
              <button
                className="link"
                onClick={() => m.setPage("Configurações")}
              >
                {step.action}
              </button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function Overview({ m }: { m: Monitor }) {
  const { sites } = useSites(m);
  const selectedSites = sites.filter(
    (s) => s.enabled && (!m.front || s.front_id === m.front),
  );
  const [tab, setTab] = useState<QueueTab>("Hoje");
  const hasMail = m.inbox.length > 0 || m.accounts.length > 0;
  const actionable = m.inbox.filter(
    (e) =>
      !e.demand_id &&
      ["acao", "importante"].includes(e.analysis?.importancia ?? ""),
  );
  const metrics = [
    {
      label: "Demandas abertas",
      value: m.open.length,
      caption: `${m.dueToday.length} para hoje ou em atraso`,
      icon: Workflow,
    },
    {
      label: "E-mails para agir",
      value: hasMail ? actionable.length : "—",
      caption: hasMail
        ? `${m.inbox.length} na caixa unificada`
        : "Nenhuma conta conectada",
      icon: Mail,
    },
    {
      label: "Sites disponíveis",
      value: m.preview
        ? m.front
          ? "1 / 1"
          : "4 / 4"
        : selectedSites.length
          ? `${selectedSites.filter((s) => fresh(s) && s.latest?.ok).length} / ${selectedSites.length}`
          : "—",
      caption: m.preview
        ? "Dados de demonstração"
        : selectedSites.length
          ? "Checagens locais recentes (até 5 min)"
          : "Cadastre seus sites",
      icon: Globe,
    },
    {
      label: "Mensagens pendentes",
      value: m.preview ? (m.front ? [3, 2, 1, 1][m.front - 1] : 7) : "—",
      caption: m.preview ? "Dados de demonstração" : "Redes sociais em breve",
      icon: MessageSquare,
    },
  ];
  return (
    <>
      {m.connected && !m.preview && <FirstSteps m={m} />}
      <div className="metrics">
        {metrics.map(({ label, value, caption, icon: Icon }) => (
          <div className="metric" key={label}>
            <div>
              <span>{label}</span>
              <Icon size={18} aria-hidden />
            </div>
            <strong>{value}</strong>
            <small>{caption}</small>
          </div>
        ))}
      </div>
      <Panel
        title="Sua fila de trabalho"
        action={
          <button className="ghost sm" onClick={() => m.setPage("Demandas")}>
            Ver todas
            <ArrowUpRight size={16} />
          </button>
        }
      >
        <Tabs<QueueTab>
          label="Fila de trabalho"
          value={tab}
          onChange={setTab}
          items={[
            { id: "Hoje", count: m.dueToday.length },
            { id: "Todas", count: m.open.length },
            { id: "Sugestões da IA", count: m.suggested.length },
          ]}
        />
        {tab !== "Sugestões da IA" ? (
          <DemandRows items={tab === "Hoje" ? m.dueToday : m.open} m={m} />
        ) : m.suggested.length ? (
          <div>
            {m.suggested.map((s) => (
              <div className="row" key={s.id}>
                <span className="row-icon">
                  <Sparkles size={18} aria-hidden />
                </span>
                <span className="row-body">
                  <strong className="truncate">{s.title}</strong>
                  <small className="truncate">
                    {frontLabel(s.front_id)} · {senderName(s.contact)}
                    {s.due && ` · prazo ${dateLabel(s.due)}`}
                  </small>
                </span>
                <button
                  className="primary sm"
                  onClick={() => void m.acceptSuggestion(s)}
                >
                  Criar demanda
                </button>
                <button
                  className="ghost sm"
                  onClick={() => void m.dismissSuggestion(s)}
                >
                  Descartar
                </button>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            icon={Sparkles}
            text="Nenhuma sugestão no momento. Quando um e-mail pedir uma ação, ele aparece aqui para você aceitar ou descartar."
          />
        )}
      </Panel>
      <div className="grid-2">
        <Panel title="E-mails → demandas" action={m.preview && sample}>
          {actionable.length ? (
            <div>
              {actionable.slice(0, 5).map((e) => (
                <div className="row" key={e.id}>
                  <span className="row-icon">
                    <Mail size={18} aria-hidden />
                  </span>
                  <span className="row-body">
                    <strong className="truncate">{e.subject}</strong>
                    <small className="truncate">
                      {frontLabel(e.front_id)} · {senderName(e.sender)} ·{" "}
                      {importanceLabels[e.analysis!.importancia]}
                    </small>
                  </span>
                  <button className="sm" onClick={() => m.emailToDemand(e)}>
                    <Plus size={16} />
                    Demanda
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              icon={Mail}
              text={
                hasMail
                  ? "Nenhum e-mail aguardando uma decisão sua."
                  : "Conecte suas contas para ver aqui os e-mails que pedem ação."
              }
            />
          )}
          <button className="panel-foot" onClick={() => m.setPage("E-mails")}>
            Abrir caixa unificada
            <ArrowRight size={16} />
          </button>
        </Panel>
        <Panel title="Saúde dos sites" action={m.preview ? sample : undefined}>
          {m.preview ? (
            <div>
              {[1, 2, 3, 4]
                .filter((n) => !m.front || m.front === n)
                .map((n) => (
                  <div className="row" key={n}>
                    <span className="row-icon">
                      <Globe size={18} aria-hidden />
                    </span>
                    <span className="row-body">
                      <strong>frente0{n}.example</strong>
                      <small>Online</small>
                    </span>
                    <span className="row-meta">{180 + n * 17} ms</span>
                    <span className="dot" />
                  </div>
                ))}
            </div>
          ) : selectedSites.length ? (
            selectedSites.map((site) => (
              <button
                className="row"
                key={site.id}
                onClick={() => m.setPage("Sites")}
              >
                <Globe size={18} aria-hidden />
                <span className="row-body">
                  <strong>{site.name}</strong>
                  <small>{siteStatus(site)}</small>
                </span>
                <span className="row-meta">
                  {site.latest?.latency_ms === null || !site.latest
                    ? "—"
                    : `${site.latest.latency_ms} ms`}
                </span>
              </button>
            ))
          ) : (
            <Empty
              icon={Globe}
              text="Cadastre seus sites para acompanhar as checagens aqui."
            />
          )}
          <button className="panel-foot" onClick={() => m.setPage("Sites")}>
            Ver monitoramento
            <ArrowRight size={16} />
          </button>
        </Panel>
      </div>
      <Panel title="Redes sociais" action={m.preview ? sample : soon}>
        <SocialTable m={m} />
      </Panel>
      <p className="footnote">
        <span className="dot" /> Seus dados ficam neste computador. Nenhum
        conteúdo é enviado para serviços de IA na nuvem.
      </p>
    </>
  );
}

export function SocialTable({ m }: { m: Monitor }) {
  if (!m.preview)
    return (
      <Empty
        icon={Activity}
        text="Instagram e WhatsApp serão conectados pelas integrações oficiais em uma próxima versão."
      />
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Perfil</th>
            <th>Seguidores</th>
            <th>Variação 7 dias</th>
            <th>Mensagens</th>
          </tr>
        </thead>
        <tbody>
          {[2480, 1820, 965, 3210].map(
            (followers, i) =>
              (!m.front || m.front === i + 1) && (
                <tr key={i}>
                  <td>
                    <strong>@frente0{i + 1}</strong>
                  </td>
                  <td>{followers.toLocaleString("pt-BR")}</td>
                  <td>+{[124, 68, 32, 146][i]}</td>
                  <td>{[3, 2, 1, 1][i]} pendentes</td>
                </tr>
              ),
          )}
        </tbody>
      </table>
    </div>
  );
}
