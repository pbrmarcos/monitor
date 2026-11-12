import { Activity, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, SocialProfile } from "../api";
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
}: {
  profile: SocialProfile;
  onSync?: () => Promise<void>;
  onRemove?: () => Promise<void>;
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
          : "Novos seguidores",
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
            disabled={busy}
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
      {profile.status === "erro" && (
        <Callout tone="error" role="alert">
          {profile.status_detail}
        </Callout>
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
  const real = m.connected && !m.preview;
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
                        .then(replace)
                        .catch(m.fail)
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
                : "Nenhum perfil conectado. Conecte um Instagram profissional abaixo para acompanhar seguidores, posts e stories."
            }
          />
        </section>
      )}
      {!m.preview && (
        <Panel
          title="Conectar Instagram"
          action={<span className="badge">Somente leitura</span>}
        >
          <div className="panel-body">
            <p>
              O Monitor consulta a API oficial do Instagram uma vez por hora,
              sem navegador e sem publicar nada. A conta precisa ser
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
      )}
    </>
  );
}
