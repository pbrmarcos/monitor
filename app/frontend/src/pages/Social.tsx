import { Activity, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api, BrowserProfile, SocialComment, SocialProfile } from "../api";
import { isTauri } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import type { Monitor } from "../store";
import { Avatar, Callout, Empty, frontLabel, Panel, timeLabel } from "../ui";

const number = (value: number | null) =>
  value === null ? "—" : value.toLocaleString("pt-BR");
const signed = (value: number | null) =>
  value === null ? "—" : `${value > 0 ? "+" : ""}${number(value)}`;

export function ProfileCard({
  profile,
  onSync,
  onRemove,
  onSettings,
}: {
  profile: SocialProfile;
  onSync?: () => Promise<void>;
  onRemove?: () => Promise<void>;
  onSettings?: (enabled: boolean, auto: boolean) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    await action().finally(() => setBusy(false));
  };
  const change = profile.followers_change;
  const week = [
    {
      label:
        profile.change_days && profile.change_days < 7
          ? `Seguidores em ${profile.change_days} ${profile.change_days === 1 ? "dia" : "dias"}`
          : "Variação de seguidores",
      value: signed(change),
      tone: change === null || change === 0 ? "" : change > 0 ? "up" : "down",
    },
    { label: "Posts", value: number(profile.posts_week) },
    { label: "Stories", value: number(profile.stories_week) },
    { label: "Curtidas", value: number(profile.likes_week) },
    { label: "Comentários", value: number(profile.comments_week) },
  ];
  return (
    <article className="social-card" aria-label={`@${profile.username}`}>
      <header>
        <Avatar
          src={profile.avatar}
          name={profile.name || profile.username}
          size="lg"
        />
        <div>
          <strong>@{profile.username}</strong>
          <small>
            {frontLabel(profile.front_id)} · Instagram
            {profile.name && profile.name !== frontLabel(profile.front_id)
              ? ` · ${profile.name}`
              : ""}
          </small>
        </div>
        {onSync && (
          <button
            className="icon sm ghost"
            aria-label={`Atualizar @${profile.username}`}
            title="Atualizar agora"
            disabled={busy || profile.enabled === false}
            onClick={() => void run(onSync)}
          >
            <RefreshCw size={16} />
          </button>
        )}
        {onRemove && (
          <button
            className="icon sm ghost"
            aria-label={`Remover @${profile.username}`}
            title="Remover perfil"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            <Trash2 size={16} />
          </button>
        )}
      </header>
      <div className="social-totals">
        <div>
          <strong>{number(profile.followers)}</strong>
          <span>Seguidores</span>
        </div>
        <div>
          <strong>{number(profile.posts)}</strong>
          <span>Posts</span>
        </div>
      </div>
      <div className="social-week">
        <span className="eyebrow">Últimos 7 dias</span>
        <dl>
          {week.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd className={item.tone}>{item.value}</dd>
            </div>
          ))}
        </dl>
      </div>
      {profile.status_detail && (
        <Callout tone={profile.status === "erro" ? "error" : ""} role="status">
          {profile.status_detail}
        </Callout>
      )}
      {profile.method === "browser" && (
        <div className="social-browser-settings">
          <span className="badge">Chrome oculto · a cada 15 min</span>
          <p>
            Até 12 posts recentes. Os números da semana cobrem os posts
            observados; stories e Direct não são lidos.
          </p>
          {profile.comments_detail && (
            <p role="status">{profile.comments_detail}</p>
          )}
          {onSettings && (
            <>
              <label className="check">
                <input
                  type="checkbox"
                  checked={!!profile.auto_demands}
                  disabled={busy}
                  onChange={(e) =>
                    void run(() =>
                      onSettings(profile.enabled !== false, e.target.checked),
                    )
                  }
                />{" "}
                Criar demandas de novos pedidos comerciais
              </label>
              <button
                className="sm"
                disabled={busy}
                onClick={() =>
                  void run(() =>
                    onSettings(
                      profile.enabled === false,
                      !!profile.auto_demands,
                    ),
                  )
                }
              >
                {profile.enabled === false ? "Retomar coleta" : "Pausar coleta"}
              </button>
            </>
          )}
        </div>
      )}
      {confirming && onRemove ? (
        <footer>
          <span>Remover este perfil e o histórico coletado?</span>
          <button
            className="danger sm"
            disabled={busy}
            onClick={() => void run(onRemove)}
          >
            Remover
          </button>
          <button className="sm" onClick={() => setConfirming(false)}>
            Cancelar
          </button>
        </footer>
      ) : (
        <footer>
          <span>
            {profile.last_sync
              ? `Atualizado ${timeLabel(profile.last_sync)}`
              : "Aguardando a primeira coleta"}
            {change === null && profile.status !== "erro"
              ? " · a variação de seguidores aparece a partir da segunda coleta diária"
              : ""}
          </span>
        </footer>
      )}
    </article>
  );
}

export function Social({ m }: { m: Monitor }) {
  const [front, setFront] = useState(1);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [browserProfiles, setBrowserProfiles] = useState<BrowserProfile[]>([]);
  const [account, setAccount] = useState(0);
  const [automatic, setAutomatic] = useState(true);
  const [comments, setComments] = useState<SocialComment[]>([]);
  const [workingComment, setWorkingComment] = useState<number | null>(null);
  const real = m.connected && !m.preview;
  async function refresh() {
    const [profiles, records] = await Promise.all([
      api<SocialProfile[]>("/social"),
      api<SocialComment[]>("/social/comments"),
    ]);
    m.setSocial(profiles);
    setComments(records);
    await m.refreshDemands();
  }
  async function findProfiles() {
    try {
      const found = await api<BrowserProfile[]>("/social/browser/profiles");
      setBrowserProfiles(found);
      if (found.length && !account) chooseAccount(found[0]);
    } catch (error) {
      m.fail(error);
    }
  }
  function chooseAccount(profile: BrowserProfile) {
    setAccount(profile.account_id);
    const match = [1, 2, 3, 4].find(
      (n) =>
        frontLabel(n).toLocaleLowerCase() === profile.name.toLocaleLowerCase(),
    );
    if (match) setFront(match);
  }
  useEffect(() => {
    if (!real) return;
    void findProfiles();
    void refresh().catch(m.fail);
    const timer = setInterval(() => void refresh().catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, [real]);
  async function connectBrowser(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api<SocialProfile>("/social/browser", "POST", {
        account_id: account,
        front_id: front,
        auto_demands: automatic,
      });
      await refresh();
      m.setNotice(
        "Perfil conectado. Clique em atualizar para coletar agora; as próximas rodadas são a cada 15 minutos.",
      );
    } catch (error) {
      m.fail(error);
    } finally {
      setSaving(false);
    }
  }
  const profiles = m.social.filter((p) => !m.front || p.front_id === m.front);
  const replace = (profile: SocialProfile) =>
    m.setSocial((old) =>
      old.map((item) => (item.id === profile.id ? profile : item)),
    );
  async function connect(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const profile = await api<SocialProfile>("/social", "POST", {
        front_id: front,
        token: token.trim(),
      });
      m.setSocial((old) => [...old, profile]);
      setToken("");
      m.setNotice(`Perfil @${profile.username} conectado.`);
    } catch (err) {
      m.fail(err);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      {m.preview && (
        <Callout>
          Dados de demonstração. Nenhuma conta do Instagram está conectada.
        </Callout>
      )}
      {profiles.length ? (
        <div className="social-grid">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              onSync={
                real
                  ? () =>
                      api<SocialProfile>(`/social/${profile.id}/sync`, "POST")
                        .then(async (profile) => {
                          replace(profile);
                          await refresh();
                        })
                        .catch(m.fail)
                  : undefined
              }
              onSettings={
                real && profile.method === "browser"
                  ? async (enabled, auto_demands) => {
                      try {
                        replace(
                          await api<SocialProfile>(
                            `/social/${profile.id}/browser`,
                            "PUT",
                            { enabled, auto_demands },
                          ),
                        );
                      } catch (error) {
                        m.fail(error);
                      }
                    }
                  : undefined
              }
              onRemove={
                real
                  ? () =>
                      api(`/social/${profile.id}`, "DELETE")
                        .then(() => {
                          m.setSocial((old) =>
                            old.filter((item) => item.id !== profile.id),
                          );
                          m.setNotice("Perfil removido.");
                        })
                        .catch(m.fail)
                  : undefined
              }
            />
          ))}
        </div>
      ) : (
        <section className="panel">
          <Empty
            icon={Activity}
            text={
              m.social.length
                ? "Nenhum perfil conectado nesta frente."
                : "Conecte os perfis do Chrome usados pelo Instagram Prospect para acompanhar suas contas."
            }
          />
        </section>
      )}
      {!m.preview && (
        <Panel
          title="Conectar pelo Chrome do Prospect"
          action={<span className="badge">Sem token da Meta</span>}
        >
          <div className="panel-body">
            <p>
              O Monitor usa o login já salvo no Prospect, abre o Chrome sem
              janela a cada 15 minutos e fecha ao terminar. O computador e o
              Monitor precisam estar ligados. Se o perfil estiver aberto no
              Prospect, a coleta dessa conta será adiada.
            </p>
            <form
              className="form-grid"
              onSubmit={(e) => void connectBrowser(e)}
            >
              <label className="field">
                Conta do Instagram Prospect
                <select
                  value={account}
                  disabled={!real || saving}
                  onChange={(e) => {
                    const selected = browserProfiles.find(
                      (p) => p.account_id === Number(e.target.value),
                    );
                    if (selected) chooseAccount(selected);
                  }}
                  required
                >
                  <option value={0}>Selecione o perfil</option>
                  {browserProfiles.map((p) => (
                    <option key={p.account_id} value={p.account_id}>
                      @{p.username} · {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Frente
                <select
                  value={front}
                  onChange={(e) => setFront(Number(e.target.value))}
                  disabled={!real || saving}
                >
                  {[1, 2, 3, 4].map((n) => (
                    <option key={n} value={n}>
                      {frontLabel(n)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={automatic}
                  onChange={(e) => setAutomatic(e.target.checked)}
                  disabled={!real || saving}
                />{" "}
                Criar demandas de novos pedidos comerciais claros
              </label>
              <p>
                Pedidos de orçamento, preço, contratação ou suporte podem virar
                demandas. Comentários antigos ficam para revisão. Nenhuma
                resposta é enviada ao Instagram.
              </p>
              <div className="button-row">
                <button
                  className="primary"
                  disabled={!real || saving || !account}
                >
                  {saving ? "Conectando…" : "Conectar perfil do Chrome"}
                </button>
                <button
                  type="button"
                  disabled={!real || saving}
                  onClick={() => void findProfiles()}
                >
                  Buscar perfis
                </button>
              </div>
            </form>
            {!browserProfiles.length && (
              <p>
                Não há perfis disponíveis em InstagramProspect na pasta local
                deste usuário. Configure e faça login nas contas pelo Prospect
                primeiro.
              </p>
            )}
          </div>
        </Panel>
      )}
      {real && (
        <Panel
          title="Comentários coletados"
          action={
            <span className="badge">
              {
                comments.filter((c) => !m.front || c.front_id === m.front)
                  .length
              }{" "}
              recentes
            </span>
          }
        >
          {comments.filter((c) => !m.front || c.front_id === m.front).length ? (
            <div className="social-comments">
              {comments
                .filter((c) => !m.front || c.front_id === m.front)
                .map((comment) => (
                  <article key={comment.id}>
                    <header>
                      <strong>@{comment.author}</strong>
                      <span>
                        {frontLabel(comment.front_id)} ·{" "}
                        {timeLabel(comment.published_at)}
                      </span>
                    </header>
                    <p>{comment.text}</p>
                    <small>{comment.reason}</small>
                    <div className="button-row">
                      <button
                        className="ghost sm"
                        onClick={() => {
                          if (isTauri())
                            void openUrl(comment.post_url).catch(m.fail);
                          else
                            window.open(comment.post_url, "_blank", "noopener");
                        }}
                      >
                        Ver publicação ↗
                      </button>
                      {comment.demand_id ? (
                        <button
                          className="sm"
                          onClick={() => {
                            const demand = m.demands.find(
                              (d) => d.id === comment.demand_id,
                            );
                            if (demand) m.setDetail(demand);
                            else m.setPage("Demandas");
                          }}
                        >
                          Abrir demanda #{comment.demand_id}
                        </button>
                      ) : (
                        comment.status !== "descartado" && (
                          <>
                            <button
                              className="sm"
                              disabled={workingComment !== null}
                              onClick={async () => {
                                setWorkingComment(comment.id);
                                try {
                                  await api(
                                    `/social/comments/${comment.id}/accept`,
                                    "POST",
                                  );
                                  await refresh();
                                } catch (error) {
                                  m.fail(error);
                                } finally {
                                  setWorkingComment(null);
                                }
                              }}
                            >
                              Criar demanda
                            </button>
                            <button
                              className="ghost sm"
                              disabled={workingComment !== null}
                              onClick={async () => {
                                setWorkingComment(comment.id);
                                try {
                                  await api(
                                    `/social/comments/${comment.id}/dismiss`,
                                    "POST",
                                  );
                                  await refresh();
                                } catch (error) {
                                  m.fail(error);
                                } finally {
                                  setWorkingComment(null);
                                }
                              }}
                            >
                              Descartar
                            </button>
                          </>
                        )
                      )}
                    </div>
                  </article>
                ))}
            </div>
          ) : (
            <Empty
              icon={Activity}
              text="Os comentários dos posts recentes aparecerão após a primeira coleta."
            />
          )}
        </Panel>
      )}
      {!m.preview && (
        <details className="social-api-option">
          <summary>Conexão alternativa pela API da Meta</summary>
          <Panel
            title="Conectar Instagram"
            action={<span className="badge">Somente leitura</span>}
          >
            <div className="panel-body">
              <p>
                A conexão alternativa consulta a API do Instagram a cada 15
                minutos, sem navegador e sem publicar nada. A conta precisa ser
                profissional (Comercial ou Criador). Gere o token de acesso no
                painel de desenvolvedor da Meta; o passo a passo está em
                docs/REDES-SOCIAIS.md. O token fica no Gerenciador de
                Credenciais do Windows.
              </p>
              <form className="form-grid" onSubmit={(e) => void connect(e)}>
                <label className="field">
                  Frente
                  <select
                    value={front}
                    onChange={(e) => setFront(Number(e.target.value))}
                    disabled={!real}
                  >
                    {[1, 2, 3, 4].map((n) => (
                      <option key={n} value={n}>
                        {frontLabel(n)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Token de acesso do Instagram
                  <input
                    type="password"
                    autoComplete="off"
                    required
                    minLength={20}
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    disabled={!real}
                  />
                </label>
                <div className="button-row">
                  <button className="primary" disabled={!real || saving}>
                    {saving ? "Conectando…" : "Conectar perfil"}
                  </button>
                </div>
              </form>
              <p>
                WhatsApp ainda não está disponível: a leitura oficial depende de
                um parceiro da Meta.
              </p>
            </div>
          </Panel>
        </details>
      )}
    </>
  );
}
