import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  CircleCheck,
  CircleDashed,
  Globe,
  Mail,
  Workflow,
} from "lucide-react";
import { today } from "../demo";
import {
  awaitingMail,
  buildPriorities,
  groupLabels,
  groupOrder,
  mailCounts,
  PriorityItem,
  waitingLabel,
} from "../priorities";
import type { Monitor } from "../store";
import { fresh, Site, siteStatus, useSites } from "./Sites";
import {
  Avatar,
  Empty,
  frontLabel,
  Panel,
  sample,
} from "../ui";

const channelLabel = (channel: string) =>
  channel === "manual" ? "criada por você" : channel;

function ItemActions({ item, m }: { item: PriorityItem; m: Monitor }) {
  const { ref } = item;
  if (ref.type === "email")
    return (
      <>
        {ref.suggestion ? (
          <button
            className="primary sm"
            onClick={() => void m.acceptSuggestion(ref.suggestion!)}
          >
            Criar demanda
          </button>
        ) : (
          <button className="sm" onClick={() => m.emailToDemand(ref.email)}>
            Revisar e criar
          </button>
        )}
        <button className="ghost sm" onClick={() => m.setPage("E-mails")}>
          Abrir e-mail
        </button>
      </>
    );
  if (ref.type === "suggestion")
    return (
      <>
        <button
          className="primary sm"
          onClick={() => void m.acceptSuggestion(ref.suggestion)}
        >
          Criar demanda
        </button>
        <button
          className="ghost sm"
          onClick={() => void m.dismissSuggestion(ref.suggestion)}
        >
          Descartar
        </button>
      </>
    );
  if (ref.type === "demand")
    return (
      <button className="sm" onClick={() => m.setDetail(ref.demand)}>
        Abrir demanda
      </button>
    );
  if (ref.type === "site")
    return (
      <button className="sm" onClick={() => m.setPage("Sites")}>
        Ver site
      </button>
    );
  return (
    <button className="sm" onClick={() => m.setPage("Configurações")}>
      Corrigir
    </button>
  );
}

function PriorityCenter({ m, sites }: { m: Monitor; sites: Site[] }) {
  const now = Date.now();
  const items = buildPriorities({
    demands: m.visible,
    emails: m.inbox,
    suggestions: m.suggested,
    accounts: m.accounts,
    sites: m.preview ? [] : sites,
    front: m.front,
    today: today(),
    now,
  });
  const waiting = awaitingMail(m.inbox).length;
  const dueNow = items.some((i) => i.group === "hoje");
  return (
    <Panel
      title="Central de prioridades"
      action={
        <button className="ghost sm" onClick={() => m.setPage("Demandas")}>
          Ver demandas
          <ArrowUpRight size={16} />
        </button>
      }
    >
      {items.length ? (
        groupOrder.map((group) => {
          const rows = items.filter((i) => i.group === group);
          if (!rows.length) return null;
          return (
            <section
              className="priority-group"
              key={group}
              aria-label={groupLabels[group]}
            >
              <h3>
                {groupLabels[group]} <span className="badge">{rows.length}</span>
              </h3>
              {rows.map((item) => (
                <div className="row" key={item.key}>
                  <span className="row-body">
                    <strong className="truncate">{item.title}</strong>
                    <small className="truncate">
                      {frontLabel(item.front_id)} ·{" "}
                      {channelLabel(item.channel)}
                      {item.since && ` · ${waitingLabel(item.since, now)}`}
                      {item.reason && ` · ${item.reason}`}
                    </small>
                  </span>
                  <ItemActions item={item} m={m} />
                </div>
              ))}
            </section>
          );
        })
      ) : (
        <Empty icon={CircleCheck} text="Nada pede a sua atenção agora." />
      )}
      {!dueNow && (m.open.length > 0 || waiting > 0) && (
        <p className="priority-note">
          Nenhuma demanda vence hoje. Você ainda tem {m.open.length}{" "}
          {m.open.length === 1 ? "demanda aberta" : "demandas abertas"} e{" "}
          {waiting} {waiting === 1 ? "e-mail esperando" : "e-mails esperando"}{" "}
          sua decisão.
        </p>
      )}
    </Panel>
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
  const hasMail = m.inbox.length > 0 || m.accounts.length > 0;
  const counts = mailCounts(m.inbox);
  const actionable = awaitingMail(m.inbox);
  const followers = m.social.filter((p) => !m.front || p.front_id === m.front);
  const gained = followers.reduce(
    (sum, p) => sum + (p.followers_change ?? 0),
    0,
  );
  const metrics = [
    {
      label: "Demandas abertas",
      value: m.open.length,
      caption: `${m.dueToday.length} para hoje ou em atraso`,
      icon: Workflow,
    },
    {
      label: "E-mails esperando você",
      value: hasMail ? actionable.length : "—",
      caption: hasMail
        ? `${counts.acao + counts.importante} importantes ou de ação · ${counts.comDemanda} já viraram demanda`
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
      label: "Seguidores no Instagram",
      value: followers.length
        ? followers
            .reduce((sum, p) => sum + (p.followers ?? 0), 0)
            .toLocaleString("pt-BR")
        : "—",
      caption: followers.length
        ? `${followers.length} ${followers.length === 1 ? "perfil" : "perfis"} · ${gained >= 0 ? "+" : ""}${gained.toLocaleString("pt-BR")} em 7 dias`
        : "Nenhum perfil conectado",
      icon: Activity,
    },
  ];
  return (
    <>
      {m.connected && !m.preview && <FirstSteps m={m} />}
      <PriorityCenter m={m} sites={sites} />
      <div className="metrics">
        {metrics.map(({ label, value, caption, icon: Icon }) => (
          <div className="metric" key={label}>
            <div>
              <span className="metric-icon">
                <Icon size={18} aria-hidden />
              </span>
              <span>{label}</span>
            </div>
            <strong>{value}</strong>
            <small>{caption}</small>
          </div>
        ))}
      </div>
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
                      <strong>{frontLabel(n)}</strong>
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
      <Panel title="Redes sociais" action={m.preview ? sample : undefined}>
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
  const profiles = m.social.filter((p) => !m.front || p.front_id === m.front);
  if (!profiles.length)
    return (
      <Empty
        icon={Activity}
        text="Conecte seus perfis do Chrome na tela Redes sociais para acompanhar seguidores e posts."
      >
        <button className="sm" onClick={() => m.setPage("Redes sociais")}>
          Conectar perfil
        </button>
      </Empty>
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Perfil</th>
            <th>Seguidores</th>
            <th>Variação 7 dias</th>
            <th>Posts 7 dias</th>
            <th>Stories 7 dias</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => (
            <tr key={p.id}>
              <td>
                <Avatar src={p.avatar} name={p.name || p.username} />
                <strong>@{p.username}</strong>
              </td>
              <td>{p.followers?.toLocaleString("pt-BR") ?? "—"}</td>
              <td>
                {p.followers_change === null
                  ? "—"
                  : `${p.followers_change > 0 ? "+" : ""}${p.followers_change.toLocaleString("pt-BR")}`}
              </td>
              <td>{p.posts_week ?? "—"}</td>
              <td>{p.stories_week ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
