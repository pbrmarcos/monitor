import { useEffect, useState } from "react";
import { api } from "../api";
import type { Monitor } from "../store";
import { Callout, frontLabel, Panel } from "../ui";

type Config = {
  url: string;
  has_token: boolean;
  last_sync: string;
  status: string;
};
type Entry = {
  id: number;
  site_id: number;
  front_id: number;
  name: string;
  email: string;
  subject: string;
  message: string;
  received_at: string;
  status: string;
  demand_id: number | null;
};

export function Forms({ m }: { m: Monitor }) {
  const [config, setConfig] = useState<Config | null>(null),
    [url, setUrl] = useState(""),
    [token, setToken] = useState(""),
    [entries, setEntries] = useState<Entry[]>([]),
    [working, setWorking] = useState(false),
    [disconnect, setDisconnect] = useState(false);
  const [initialized, setInitialized] = useState(false);
  async function refresh() {
    if (!m.connected || m.preview) return;
    try {
      const [c, e] = await Promise.all([
        api<Config>("/relay"),
        api<Entry[]>("/forms"),
      ]);
      setConfig(c);
      setEntries(e);
      if (!initialized) {
        setUrl(c.url);
        setInitialized(true);
      }
    } catch (e) {
      m.fail(e);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 15000);
    return () => clearInterval(timer);
  }, [m.connected, m.preview, initialized]);
  async function action(work: () => Promise<unknown>) {
    setWorking(true);
    try {
      await work();
      await refresh();
      await Promise.all([m.refreshDemands(), m.refreshInbox()]);
      m.setNotice("Formulários atualizados.");
    } catch (e) {
      m.fail(e);
    } finally {
      setWorking(false);
    }
  }
  if (m.preview) return null;
  return (
    <>
      <Panel title="Formulários · conexão com o VPS">
        <form
          className="panel-body agenda-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () => {
              await api("/relay", "PUT", { url, ...(token ? { token } : {}) });
              setToken("");
            });
          }}
        >
          <p>
            Instale o relay no VPS e conecte os formulários pelos servidores dos
            sites. A coleta acontece a cada minuto; os contatos aguardam sua
            revisão antes de virar demanda.
          </p>
          <div className="form-grid">
            <label>
              Endereço do relay
              <input
                type="url"
                required
                placeholder="https://relay.seudominio.com.br"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </label>
            <label>
              Token do aplicativo
              <input
                type="password"
                autoComplete="new-password"
                minLength={32}
                maxLength={500}
                required={!config?.has_token}
                placeholder={
                  config?.has_token
                    ? "Já guardado no Windows; deixe vazio para manter"
                    : "Credencial de leitura e confirmação"
                }
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </label>
          </div>
          <small>
            O token fica no Gerenciador de Credenciais do Windows. Os tokens de
            envio de cada site ficam apenas no VPS.
          </small>
          <div className="toolbar site-actions">
            <button className="primary" disabled={working || !m.connected}>
              Salvar conexão
            </button>
            <button
              type="button"
              disabled={working || !config?.url}
              onClick={() => void action(() => api("/relay/sync", "POST"))}
            >
              Coletar agora
            </button>
            {config?.url && (
              <button
                type="button"
                className="ghost"
                onClick={() => setDisconnect(true)}
              >
                Desconectar
              </button>
            )}
          </div>
          <p>
            {config?.status || "Não configurado"}
            {config?.last_sync &&
              ` · Última coleta: ${new Date(config.last_sync).toLocaleString("pt-BR")}`}
          </p>
          {disconnect && (
            <Callout
              tone="error"
              action={
                <>
                  <button
                    type="button"
                    disabled={working}
                    onClick={() =>
                      void action(async () => {
                        await api("/relay", "PUT", { url: "" });
                        setUrl("");
                        setToken("");
                        setDisconnect(false);
                      })
                    }
                  >
                    Confirmar desconexão
                  </button>
                  <button type="button" onClick={() => setDisconnect(false)}>
                    Cancelar
                  </button>
                </>
              }
            >
              Interromper a coleta? Os contatos já recebidos serão mantidos.
            </Callout>
          )}
        </form>
      </Panel>
      <Panel title="Contatos dos formulários">
        {!entries.length && (
          <div className="panel-body">
            <p>Nenhum formulário recebido pelo relay ainda.</p>
          </div>
        )}
        {entries
          .filter((e) => !m.front || e.front_id === m.front)
          .map((entry) => (
            <div className="panel-body form-entry" key={entry.id}>
              <div className="split">
                <h3>{entry.subject}</h3>
                <span className="badge">
                  {entry.status === "pendente"
                    ? "Para revisar"
                    : entry.status === "duplicada"
                      ? "Vinculado a e-mail"
                      : entry.status === "aceita"
                        ? "Demanda criada"
                        : "Descartado"}
                </span>
              </div>
              <p>
                {entry.name} · {entry.email}
              </p>
              <small>
                {frontLabel(entry.front_id)} · Site #{entry.site_id} ·{" "}
                {new Date(entry.received_at).toLocaleString("pt-BR")}
              </small>
              <p className="form-message">{entry.message}</p>
              <div className="toolbar site-actions">
                {entry.status === "pendente" ? (
                  <>
                    <button
                      className="primary sm"
                      disabled={working}
                      onClick={() =>
                        void action(() =>
                          api(`/forms/${entry.id}/accept`, "POST"),
                        )
                      }
                    >
                      Criar demanda
                    </button>
                    <button
                      className="ghost sm"
                      disabled={working}
                      onClick={() =>
                        void action(() =>
                          api(`/forms/${entry.id}/dismiss`, "POST"),
                        )
                      }
                    >
                      Descartar contato
                    </button>
                  </>
                ) : entry.demand_id &&
                  m.demands.some((d) => d.id === entry.demand_id) ? (
                  <button
                    className="sm"
                    onClick={() =>
                      m.setDetail(
                        m.demands.find((d) => d.id === entry.demand_id)!,
                      )
                    }
                  >
                    Abrir demanda
                  </button>
                ) : null}
              </div>
            </div>
          ))}
      </Panel>
    </>
  );
}
