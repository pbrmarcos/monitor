import { useEffect, useState } from "react";
import { Globe, Plus, RefreshCw } from "lucide-react";
import { api } from "../api";
import type { Monitor } from "../store";
import { Callout, Empty, frontLabel, Panel, sample } from "../ui";
import { Forms } from "./Forms";

type Check = {
  id: number;
  ok: boolean;
  checked_at: string;
  status_code: number | null;
  latency_ms: number | null;
  detail: string;
  ssl_expires: string | null;
};
export type Site = {
  id: number;
  name: string;
  url: string;
  front_id: number;
  expected_text: string;
  enabled: boolean;
  latest: Check | null;
  samples: number;
  success_percent: number | null;
  average_ms: number | null;
  observed_since: string | null;
};
type SiteInput = Pick<
  Site,
  "name" | "url" | "front_id" | "expected_text" | "enabled"
>;
type History = {
  checks: Check[];
  incidents: {
    id: number;
    opened_at: string;
    closed_at: string | null;
    detail: string;
  }[];
};
const empty = (): SiteInput => ({
  name: "",
  url: "https://",
  front_id: 1,
  expected_text: "",
  enabled: true,
});
const dateTime = (value: string | null) =>
  value
    ? new Date(value).toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "Ainda não verificado";
export const fresh = (site: Site) =>
  !!site.latest && Date.now() - Date.parse(site.latest.checked_at) < 5 * 60_000;
export const siteStatus = (site: Site) =>
  !site.enabled
    ? "Pausado"
    : !site.latest
      ? "Aguardando checagem"
      : !fresh(site)
        ? "Checagem antiga"
        : site.latest.ok
          ? "Respondendo"
          : "Falha detectada";

export function useSites(m: Monitor) {
  const [sites, setSites] = useState<Site[]>([]);
  async function refresh() {
    if (!m.connected || m.preview) return;
    try {
      setSites(await api<Site[]>("/sites"));
    } catch (e) {
      m.fail(e);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 15000);
    return () => clearInterval(timer);
  }, [m.connected, m.preview]);
  return { sites, refresh };
}

export function Sites({ m }: { m: Monitor }) {
  const { sites, refresh } = useSites(m);
  const [form, setForm] = useState<SiteInput>(empty),
    [editing, setEditing] = useState<number | null>(null),
    [working, setWorking] = useState(false);
  const [suggestions, setSuggestions] = useState<SiteInput[]>([]),
    [history, setHistory] = useState<{ name: string; data: History } | null>(
      null,
    ),
    [removing, setRemoving] = useState<number | null>(null);
  useEffect(() => {
    if (m.connected && !m.preview)
      api<SiteInput[]>("/sites/suggestions").then(setSuggestions).catch(m.fail);
  }, [m.connected, m.preview]);
  async function action(work: () => Promise<unknown>) {
    setWorking(true);
    try {
      await work();
      await refresh();
      m.setNotice("Monitoramento atualizado.");
    } catch (e) {
      m.fail(e);
    } finally {
      setWorking(false);
    }
  }
  if (m.preview)
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
                  <p>Respondendo · exemplo fictício</p>
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
  return (
    <>
      <Callout>
        Checagens a cada 2 minutos com o Monitor aberto. O percentual representa
        as amostras coletadas nos últimos 30 dias. Períodos com o computador
        desligado ficam sem medição.
      </Callout>
      <Panel title={editing ? "Editar site" : "Adicionar site"}>
        <form
          className="panel-body agenda-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () => {
              await api(
                editing ? `/sites/${editing}` : "/sites",
                editing ? "PUT" : "POST",
                form,
              );
              setForm(empty());
              setEditing(null);
            });
          }}
        >
          {!editing && suggestions.length > 0 && (
            <label>
              Seus endereços
              <select
                aria-label="Usar endereço informado"
                value={String(
                  suggestions.findIndex(
                    (s) => s.url === form.url && s.name === form.name,
                  ),
                )}
                onChange={(e) => {
                  const selected = suggestions[Number(e.target.value)];
                  if (selected)
                    setForm({ ...selected, expected_text: "", enabled: true });
                }}
              >
                <option value="-1" disabled>
                  Escolha um dos sites informados
                </option>
                {suggestions.map((s, i) => (
                  <option value={i} key={s.url}>
                    {s.name} · {s.url}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="form-grid">
            <label>
              Nome
              <input
                required
                maxLength={100}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Frente
              <select
                value={form.front_id}
                onChange={(e) =>
                  setForm({ ...form, front_id: Number(e.target.value) })
                }
              >
                {[1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>
                    {frontLabel(n)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Endereço
              <input
                required
                type="url"
                maxLength={1000}
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
              />
            </label>
            <label>
              Texto esperado (opcional)
              <input
                maxLength={500}
                placeholder="Uma frase que deve aparecer na página"
                value={form.expected_text}
                onChange={(e) =>
                  setForm({ ...form, expected_text: e.target.value })
                }
              />
            </label>
          </div>
          <div className="toolbar">
            <button className="primary" disabled={working || !m.connected}>
              <Plus size={16} />
              {editing ? "Salvar alterações" : "Adicionar site"}
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => {
                  setEditing(null);
                  setForm(empty());
                }}
              >
                Cancelar edição
              </button>
            )}
          </div>
        </form>
      </Panel>
      {!sites.length && (
        <Panel title="Seus sites">
          <Empty
            icon={Globe}
            text="Cadastre os endereços para começar a acompanhar disponibilidade e certificado."
          />
        </Panel>
      )}
      <div className="grid-2">
        {sites
          .filter((s) => !m.front || s.front_id === m.front)
          .map((site) => (
            <Panel
              key={site.id}
              title={site.name}
              action={<span className="badge">{siteStatus(site)}</span>}
            >
              <div className="panel-body site-card">
                <p className="path">{site.url}</p>
                <small>
                  {frontLabel(site.front_id)} · Site #{site.id} · Última
                  checagem: {dateTime(site.latest?.checked_at ?? null)}
                </small>
                <dl className="facts">
                  <div>
                    <dt>Amostras bem-sucedidas</dt>
                    <dd>
                      {site.success_percent === null
                        ? "—"
                        : `${site.success_percent}%`}
                    </dd>
                  </div>
                  <div>
                    <dt>Resposta média</dt>
                    <dd>
                      {site.average_ms === null ? "—" : `${site.average_ms} ms`}
                    </dd>
                  </div>
                  <div>
                    <dt>Certificado válido até</dt>
                    <dd>
                      {site.latest?.ssl_expires
                        ? new Date(site.latest.ssl_expires).toLocaleDateString(
                            "pt-BR",
                          )
                        : "Sem informação"}
                    </dd>
                  </div>
                  <div>
                    <dt>Coleta iniciada</dt>
                    <dd>{dateTime(site.observed_since)}</dd>
                  </div>
                </dl>
                <p>
                  {site.latest?.detail ||
                    "A primeira checagem será executada na próxima rodada."}{" "}
                  {site.samples} amostra(s).
                </p>
                <div className="toolbar site-actions">
                  <button
                    className="sm"
                    disabled={working || !site.enabled}
                    onClick={() =>
                      void action(() => api(`/sites/${site.id}/check`, "POST"))
                    }
                  >
                    <RefreshCw size={16} />
                    Verificar agora
                  </button>
                  <button
                    className="ghost sm"
                    disabled={working}
                    onClick={() => {
                      setEditing(site.id);
                      setForm({
                        name: site.name,
                        url: site.url,
                        front_id: site.front_id,
                        expected_text: site.expected_text,
                        enabled: site.enabled,
                      });
                    }}
                  >
                    Editar
                  </button>
                  <button
                    className="ghost sm"
                    disabled={working}
                    onClick={() =>
                      void action(() =>
                        api(`/sites/${site.id}`, "PUT", {
                          name: site.name,
                          url: site.url,
                          front_id: site.front_id,
                          expected_text: site.expected_text,
                          enabled: !site.enabled,
                        }),
                      )
                    }
                  >
                    {site.enabled ? "Pausar" : "Retomar"}
                  </button>
                  <button
                    className="ghost sm"
                    disabled={working}
                    onClick={() =>
                      void action(async () =>
                        setHistory({
                          name: site.name,
                          data: await api<History>(`/sites/${site.id}/history`),
                        }),
                      )
                    }
                  >
                    Histórico
                  </button>
                  <button
                    className="ghost sm"
                    onClick={() => setRemoving(site.id)}
                  >
                    Excluir
                  </button>
                </div>
                {removing === site.id && (
                  <Callout
                    tone="error"
                    action={
                      <>
                        <button
                          className="sm"
                          disabled={working}
                          onClick={() =>
                            void action(async () => {
                              await api(`/sites/${site.id}`, "DELETE");
                              setRemoving(null);
                              setHistory(null);
                            })
                          }
                        >
                          Confirmar exclusão
                        </button>
                        <button
                          className="sm"
                          onClick={() => setRemoving(null)}
                        >
                          Cancelar
                        </button>
                      </>
                    }
                  >
                    Excluir este site e seu histórico?
                  </Callout>
                )}
              </div>
            </Panel>
          ))}
      </div>
      <Forms m={m} />
      {history && (
        <Panel
          title={`Histórico · ${history.name}`}
          action={
            <button className="ghost sm" onClick={() => setHistory(null)}>
              Fechar histórico
            </button>
          }
        >
          <div className="panel-body">
            <h3>Incidentes</h3>
            {!history.data.incidents.length ? (
              <p>Nenhum incidente registrado.</p>
            ) : (
              history.data.incidents.map((i) => (
                <p key={i.id}>
                  {dateTime(i.opened_at)} →{" "}
                  {i.closed_at ? dateTime(i.closed_at) : "Em aberto"} ·{" "}
                  {i.detail}
                </p>
              ))
            )}
          </div>
          <div className="table-wrap">
            <table>
              <caption>Últimas 100 checagens</caption>
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Resultado</th>
                  <th>HTTP</th>
                  <th>Resposta</th>
                </tr>
              </thead>
              <tbody>
                {history.data.checks.map((c) => (
                  <tr key={c.id}>
                    <td>{dateTime(c.checked_at)}</td>
                    <td>{c.detail}</td>
                    <td>{c.status_code ?? "—"}</td>
                    <td>
                      {c.latency_ms === null ? "—" : `${c.latency_ms} ms`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
