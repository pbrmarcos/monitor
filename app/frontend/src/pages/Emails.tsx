import {
  Check,
  CircleAlert,
  Mail,
  Paperclip,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { api, categoryLabels, Email, importanceLabels } from "../api";
import type { Monitor } from "../store";
import { ReplyBox } from "./Reply";
import {
  Callout,
  dateLabel,
  Empty,
  frontLabel,
  Panel,
  senderName,
  Tabs,
  timeLabel,
} from "../ui";

const tabs = [
  "Todos",
  "Importantes",
  "Precisam de ação",
  "Revisar",
  "Informativos",
] as const;
type Tab = (typeof tabs)[number];
const inTab = (e: Email, tab: Tab) => {
  const level = e.analysis?.importancia ?? "revisar";
  if (tab === "Todos") return true;
  if (tab === "Importantes") return level === "importante" || level === "acao";
  if (tab === "Precisam de ação") return level === "acao";
  return tab === "Revisar" ? level === "revisar" : level === "info";
};

export function Emails({ m }: { m: Monitor }) {
  const [tab, setTab] = useState<Tab>("Todos");
  const [account, setAccount] = useState(0);
  const [selected, setSelected] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const scoped = m.inbox.filter((e) => !account || e.account_id === account);
  const list = scoped.filter((e) => inTab(e, tab));
  const current = list.find((e) => e.id === selected) ?? list[0];
  const failing = m.accounts.filter((a) => a.status === "erro");

  async function sync() {
    setSyncing(true);
    try {
      const result = await api<{ new: number }>("/emails/sync", "POST");
      await m.refreshInbox();
      m.setNotice(
        result.new
          ? `${result.new} mensagem(ns) nova(s).`
          : "Nenhuma mensagem nova.",
      );
    } catch (e) {
      m.fail(e);
    } finally {
      setSyncing(false);
    }
  }

  if (!m.inbox.length && !m.accounts.length)
    return (
      <Panel title="Caixa unificada">
        <Empty
          icon={Mail}
          text="Conecte as caixas de e-mail das suas frentes. O Monitor apenas lê as mensagens: não marca como lida, não move e não apaga."
        >
          <button
            className="primary"
            onClick={() => m.setPage("Configurações")}
          >
            Conectar conta de e-mail
          </button>
        </Empty>
      </Panel>
    );

  return (
    <>
      {failing.map((a) => (
        <Callout key={a.id} icon={CircleAlert} tone="error" role="alert">
          <strong>{a.address}</strong> · {a.status_detail}
        </Callout>
      ))}
      {m.pendingAi > 0 && (
        <Callout icon={Sparkles}>
          <strong>{m.pendingAi} mensagem(ns) na fila da IA.</strong> Enquanto
          isso, a classificação vem das regras e fica marcada como provisória.
        </Callout>
      )}
      <div className="toolbar">
        <select
          aria-label="Conta de e-mail"
          value={account}
          onChange={(e) => setAccount(Number(e.target.value))}
        >
          <option value={0}>Todas as contas</option>
          {[...new Map(m.inbox.map((e) => [e.account_id, e.account]))].map(
            ([id, address]) => (
              <option key={id} value={id}>
                {address}
              </option>
            ),
          )}
        </select>
        {m.connected && !m.preview && (
          <button onClick={() => void sync()} disabled={syncing}>
            <RefreshCw size={16} />
            {syncing ? "Verificando…" : "Verificar agora"}
          </button>
        )}
      </div>
      <section className="panel">
        <Tabs<Tab>
          label="Filtro de importância"
          value={tab}
          onChange={setTab}
          items={tabs.map((id) => ({
            id,
            count: scoped.filter((e) => inTab(e, id)).length,
          }))}
        />
        {current ? (
          <div className="mail">
            <div className="mail-list">
              {list.map((e) => (
                <button
                  key={e.id}
                  className="mail-item"
                  aria-current={e.id === current.id}
                  onClick={() => setSelected(e.id)}
                >
                  <div>
                    <strong className="truncate">{senderName(e.sender)}</strong>
                    <span className="caption">{timeLabel(e.date)}</span>
                  </div>
                  <span className="truncate">{e.subject}</span>
                  <div>
                    <span className="caption">{frontLabel(e.front_id)}</span>
                    <ImportanceTag email={e} />
                  </div>
                </button>
              ))}
            </div>
            <Reader email={current} m={m} />
          </div>
        ) : (
          <Empty icon={Mail} text="Nenhuma mensagem neste filtro." />
        )}
      </section>
    </>
  );
}

function ImportanceTag({ email }: { email: Email }) {
  const level = email.analysis?.importancia ?? "revisar";
  return <span className={`tag ${level}`}>{importanceLabels[level]}</span>;
}

function Reader({ email, m }: { email: Email; m: Monitor }) {
  const a = email.analysis;
  return (
    <article className="mail-reader">
      <div>
        <span className="eyebrow">
          {frontLabel(email.front_id)} · {email.account}
        </span>
        <h2>{email.subject}</h2>
        <p className="muted small">
          {email.sender}
          {email.date && ` · ${new Date(email.date).toLocaleString("pt-BR")}`}
          {email.has_attachments && (
            <>
              {" · "}
              <Paperclip size={14} aria-label="Com anexos" />
            </>
          )}
        </p>
      </div>
      <p className="mail-body">{email.body || "Mensagem sem texto."}</p>
      {a && (
        <section className="analysis">
          <header>
            <h3>
              <Sparkles size={18} aria-hidden />
              Análise da mensagem
            </h3>
            <span className={a.provisional ? "badge" : "badge ai"}>
              {a.provisional ? "Provisória · regras" : "IA local"}
            </span>
          </header>
          <dl className="facts">
            <div>
              <dt>Classificação</dt>
              <dd>
                {categoryLabels[a.categoria] ?? a.categoria} ·{" "}
                {importanceLabels[a.importancia]}
              </dd>
            </div>
            <div>
              <dt>Prazo identificado</dt>
              <dd>
                {a.prazo_iso
                  ? `${dateLabel(a.prazo_iso)} (“${a.prazo_texto}”)`
                  : a.prazo_texto
                    ? `“${a.prazo_texto}” · data a confirmar`
                    : "Nenhum"}
              </dd>
            </div>
            <div className="wide">
              <dt>Motivo</dt>
              <dd>{a.motivo || "Sem observações."}</dd>
            </div>
            {a.trecho_prazo && (
              <div className="wide">
                <dt>Trecho do prazo</dt>
                <dd>“{a.trecho_prazo}”</dd>
              </div>
            )}
            {a.acao_sugerida && (
              <div className="wide">
                <dt>Ação sugerida</dt>
                <dd>{a.acao_sugerida}</dd>
              </div>
            )}
          </dl>
          {!a.provisional && (
            <p className="muted caption">
              Modelo {a.modelo} · confiança {Math.round(a.confianca * 100)}%
            </p>
          )}
        </section>
      )}
      <div className="button-row">
        {email.demand_id ? (
          <span className="badge success">
            <Check size={14} /> Demanda criada
          </span>
        ) : (
          <button className="primary" onClick={() => m.emailToDemand(email)}>
            <Plus size={16} />
            Criar demanda
          </button>
        )}
        <button
          aria-pressed={a?.correcao === "importante"}
          onClick={() => void m.correctEmail(email, "importante")}
        >
          Marcar importante
        </button>
        <button
          aria-pressed={a?.correcao === "nao_importante"}
          onClick={() => void m.correctEmail(email, "nao_importante")}
        >
          Não é importante
        </button>
      </div>
      <ReplyBox key={email.id} email={email} m={m} />
    </article>
  );
}
