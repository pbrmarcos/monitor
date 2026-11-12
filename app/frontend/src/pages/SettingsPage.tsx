import {
  ArrowDownToLine,
  ArrowUpRight,
  Cloud,
  FolderOpen,
  HardDrive,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  Account,
  AccountInput,
  api,
  AppSettings,
  Calendar,
  Ollama,
  pullModel,
  Storage,
} from "../api";
import type { Monitor } from "../store";
import { Personalization, Updates } from "./Personalization";
import { Callout, frontLabel, Panel, soon } from "../ui";

const OLLAMA_URL = "https://ollama.com/download/windows";
const emptyAccount = (): AccountInput => ({
  front_id: 1,
  address: "",
  host: "",
  port: 993,
  username: "",
  password: "",
});

export function SettingsPage({ m }: { m: Monitor }) {
  const offline = !m.connected;
  return (
    <div className="settings">
      {offline && (
        <div className="wide">
          <Callout>
            Na prévia do navegador as configurações não são salvas. Abra o
            aplicativo desktop para conectar contas e escolher a pasta.
          </Callout>
        </div>
      )}
      <FilesFolder m={m} />
      <Accounts m={m} />
      <LocalAi m={m} />
      <GoogleCalendar m={m} />
      <Rules m={m} />
      <Panel title="Lembretes e resumo diário">
        <div className="panel-body">
          <p>
            Defina horários, consulte os avisos e escolha se os detalhes
            aparecem nas notificações do Windows.
          </p>
          <button onClick={() => m.setPage("Lembretes")}>Abrir agenda</button>
        </div>
      </Panel>
      <Personalization m={m} />
      <Application version={m.version} />
    </div>
  );
}

function FilesFolder({ m }: { m: Monitor }) {
  const [path, setPath] = useState("");
  const [working, setWorking] = useState(false);
  const storage = m.storage;
  useEffect(() => {
    setPath(storage?.files_dir ?? storage?.suggestion ?? "");
  }, [storage?.files_dir, storage?.suggestion]);

  async function run(action: () => Promise<string>) {
    setWorking(true);
    try {
      m.setNotice(await action());
      m.setStorage(await api<Storage>("/storage"));
    } catch (e) {
      m.fail(e);
    } finally {
      setWorking(false);
    }
  }
  const save = (value: string) =>
    run(async () => {
      await api<Storage>("/storage", "PUT", { files_dir: value });
      return "Pasta de arquivos salva.";
    });
  async function browse() {
    try {
      const dialog = await import("@tauri-apps/plugin-dialog");
      const chosen = await dialog.open({
        directory: true,
        defaultPath: path || undefined,
        title: "Pasta de arquivos do Monitor",
      });
      if (typeof chosen === "string") {
        setPath(chosen);
        await save(chosen);
      }
    } catch {
      m.setError(
        "Não foi possível abrir o seletor. Digite o caminho da pasta.",
      );
    }
  }

  return (
    <Panel
      title="Pasta de arquivos"
      className="wide"
      action={
        storage?.files_dir ? (
          <span className={`badge ${storage.in_onedrive ? "success" : ""}`}>
            {storage.in_onedrive ? (
              <>
                <Cloud size={14} /> No OneDrive
              </>
            ) : (
              <>
                <HardDrive size={14} /> Pasta local
              </>
            )}
          </span>
        ) : (
          <span className="badge warning">Não definida</span>
        )
      }
    >
      <div className="panel-body">
        <p>
          Backups diários, exportações e os arquivos que o Monitor organizar
          ficam nesta pasta. Escolha uma pasta dentro do OneDrive para que tudo
          seja sincronizado com a nuvem. O banco em uso permanece neste
          computador, porque sincronizá-lo aberto pode corrompê-lo; a cópia
          diária vai para a pasta.
        </p>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            void save(path);
          }}
        >
          <input
            aria-label="Caminho da pasta de arquivos"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="C:\Users\voce\OneDrive\Monitor"
            disabled={!m.connected}
          />
          {isTauri() && (
            <button type="button" onClick={() => void browse()}>
              <FolderOpen size={16} />
              Escolher…
            </button>
          )}
          <button
            className="primary"
            disabled={!m.connected || working || !path.trim()}
          >
            Salvar pasta
          </button>
        </form>
        {storage?.files_dir && !storage.in_onedrive && (
          <Callout icon={HardDrive}>
            Esta pasta não está dentro do OneDrive deste computador, então os
            arquivos não serão enviados para a nuvem.
          </Callout>
        )}
        {storage?.source === "instalador" && (
          <p>Pasta escolhida durante a instalação.</p>
        )}
        <div className="button-row">
          <button
            disabled={!storage?.files_dir || working || m.preview}
            onClick={() =>
              void run(async () => {
                await api("/storage/backup", "POST");
                return "Backup gravado na pasta de arquivos.";
              })
            }
          >
            Fazer backup agora
          </button>
          <button
            disabled={!storage?.files_dir || working}
            onClick={() =>
              void run(async () => {
                await api("/storage/export-demands", "POST");
                return "Planilha de demandas exportada.";
              })
            }
          >
            Exportar demandas (CSV)
          </button>
          <span className="muted small" style={{ alignSelf: "center" }}>
            {storage?.last_backup
              ? `Último backup: ${new Date(storage.last_backup + "T12:00:00").toLocaleDateString("pt-BR")}`
              : "Nenhum backup ainda"}
          </span>
        </div>
      </div>
    </Panel>
  );
}

function Accounts({ m }: { m: Monitor }) {
  const [form, setForm] = useState(emptyAccount);
  const [state, setState] = useState<"" | "testing" | "saving">("");
  const [tested, setTested] = useState("");
  const set = (key: keyof AccountInput, value: string | number) => {
    setTested("");
    setForm((old) => ({
      ...old,
      [key]: value,
      // O usuário IMAP quase sempre é o próprio endereço.
      ...(key === "address" && old.username === old.address
        ? { username: String(value) }
        : {}),
    }));
  };
  async function submit(e: FormEvent, test: boolean) {
    e.preventDefault();
    setState(test ? "testing" : "saving");
    try {
      if (test) {
        await api("/email-accounts/test", "POST", form);
        setTested("Conexão aceita em modo de leitura.");
      } else {
        await api<Account>("/email-accounts", "POST", form);
        setForm(emptyAccount());
        await api("/emails/sync", "POST").catch(() => {});
        await m.refreshInbox();
        m.setNotice("Conta conectada. As mensagens recentes foram coletadas.");
      }
    } catch (err) {
      m.fail(err);
    } finally {
      setState("");
    }
  }
  async function remove(account: Account) {
    try {
      await api(`/email-accounts/${account.id}`, "DELETE");
      await m.refreshInbox();
      m.setNotice("Conta removida deste computador.");
    } catch (err) {
      m.fail(err);
    }
  }
  const locked = !m.connected || m.preview;
  return (
    <Panel
      title="Contas de e-mail"
      className="wide"
      action={<span className="badge">Somente leitura</span>}
    >
      <div className="panel-body">
        <p>
          O Monitor lê a caixa de entrada por IMAP a cada 2 minutos. Ele não
          marca mensagens como lidas, não move e não apaga. A senha fica no
          Gerenciador de Credenciais do Windows e nunca é enviada à IA.
        </p>
        {m.accounts.length > 0 && (
          <div>
            {m.accounts.map((a) => (
              <div className="account" key={a.id}>
                <span
                  className={`dot ${a.status === "erro" ? "bad" : a.status === "ok" ? "" : "off"}`}
                />
                <span className="row-body">
                  <strong>{a.address}</strong>
                  <small>
                    {frontLabel(a.front_id)} · {a.host}:{a.port} ·{" "}
                    {a.status === "erro"
                      ? a.status_detail
                      : a.last_sync
                        ? `verificada ${new Date(a.last_sync).toLocaleString("pt-BR")}`
                        : a.status === "demonstracao"
                          ? "conta de demonstração"
                          : "aguardando a primeira verificação"}
                  </small>
                </span>
                {!locked && (
                  <button
                    className="icon sm ghost"
                    aria-label={`Remover ${a.address}`}
                    onClick={() => void remove(a)}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        <hr />
        <form className="form-grid" onSubmit={(e) => void submit(e, false)}>
          <label className="field">
            Endereço de e-mail
            <input
              type="email"
              required
              value={form.address}
              onChange={(e) => set("address", e.target.value)}
              placeholder="contato@seudominio.com.br"
              disabled={locked}
            />
          </label>
          <label className="field">
            Frente
            <select
              value={form.front_id}
              onChange={(e) => set("front_id", Number(e.target.value))}
              disabled={locked}
            >
              {[1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>
                  {frontLabel(n)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Servidor IMAP
            <input
              required
              value={form.host}
              onChange={(e) => set("host", e.target.value.trim())}
              placeholder="mail.seudominio.com.br"
              disabled={locked}
            />
          </label>
          <label className="field">
            Porta (SSL)
            <input
              type="number"
              required
              min={1}
              max={65535}
              value={form.port}
              onChange={(e) => set("port", Number(e.target.value))}
              disabled={locked}
            />
          </label>
          <label className="field">
            Usuário
            <input
              required
              value={form.username}
              onChange={(e) => set("username", e.target.value)}
              autoComplete="off"
              disabled={locked}
            />
          </label>
          <label className="field">
            Senha
            <input
              type="password"
              required
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              autoComplete="new-password"
              disabled={locked}
            />
          </label>
          <div className="button-row">
            <button className="primary" disabled={locked || state !== ""}>
              {state === "saving" ? "Conectando…" : "Adicionar conta"}
            </button>
            <button
              type="button"
              disabled={locked || state !== ""}
              onClick={(e) => {
                if (e.currentTarget.form?.reportValidity())
                  void submit(e, true);
              }}
            >
              {state === "testing" ? "Testando…" : "Testar conexão"}
            </button>
          </div>
          {tested && (
            <p role="status" className="small" style={{ alignSelf: "center" }}>
              <span className="dot" /> {tested}
            </p>
          )}
        </form>
      </div>
    </Panel>
  );
}

function Rules({ m }: { m: Monitor }) {
  const [value, setValue] = useState("");
  const senders = m.settings.priority_senders;
  async function save(next: string[]) {
    try {
      m.setSettings(
        await api<AppSettings>("/settings", "PUT", { priority_senders: next }),
      );
    } catch (e) {
      m.fail(e);
    }
  }
  return (
    <Panel title="Regras de importância">
      <div className="panel-body">
        <p>
          Estas regras valem mais que a opinião da IA. Pedido de orçamento ou
          prazo com data vira “Precisa de ação”; confiança baixa ou data ambígua
          vai para “Revisar”; publicidade fica como informativo.
        </p>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) void save([...senders, value]);
            setValue("");
          }}
        >
          <input
            aria-label="Remetente prioritário"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="cliente@empresa.com ou @empresa.com"
            disabled={!m.connected}
          />
          <button disabled={!m.connected || !value.trim()}>Adicionar</button>
        </form>
        {senders.length ? (
          <div className="chips">
            {senders.map((s) => (
              <span className="tag" key={s}>
                {s}
                <button
                  aria-label={`Remover ${s}`}
                  onClick={() => void save(senders.filter((x) => x !== s))}
                >
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p>
            Nenhum remetente prioritário. Mensagens deles sempre aparecem no
            mínimo como “Importante”.
          </p>
        )}
      </div>
    </Panel>
  );
}

const GOOGLE_CONSOLE = "https://console.cloud.google.com/apis/credentials";
const openExternal = (url: string) =>
  isTauri() ? void openUrl(url) : window.open(url, "_blank", "noopener");

function GoogleCalendar({ m }: { m: Monitor }) {
  const [state, setState] = useState<Calendar | null>(null);
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const { connected, setNotice } = m;
  const refresh = () =>
    api<Calendar>("/calendar").then((value) => {
      setState(value);
      return value;
    });
  useEffect(() => {
    if (!connected) return;
    api<Calendar>("/calendar")
      .then((value) => {
        setState(value);
        setClientId(value.client_id);
      })
      .catch(() => {});
  }, [connected]);
  // Enquanto o navegador está na tela do Google, confere se a conexão terminou.
  useEffect(() => {
    if (!waiting) return;
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      api<Calendar>("/calendar")
        .then((value) => {
          setState(value);
          if (value.connected) {
            setWaiting(false);
            setNotice("Agenda conectada. Enviando as demandas…");
            void api("/calendar/sync", "POST")
              .then(() => api<Calendar>("/calendar"))
              .then(setState)
              .catch(() => {});
          } else if (value.error || tries > 150) setWaiting(false);
        })
        .catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [waiting, setNotice]);
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      await refresh();
    } catch (e) {
      m.fail(e);
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  };
  const disabled = !m.connected || m.preview || busy;
  return (
    <Panel
      title="Google Agenda"
      action={
        <span className={`badge ${state?.connected ? "success" : ""}`}>
          {state?.connected ? "Conectada" : "Não conectada"}
        </span>
      }
    >
      <div className="panel-body">
        <p>
          Cada demanda aberta com prazo ou data de retorno vira um evento de
          dia inteiro na sua agenda. O Monitor só grava os próprios eventos;
          não lê nem altera os seus compromissos. Vão para o Google o título,
          a frente, a etapa e a próxima ação.
        </p>
        {state?.error && (
          <Callout tone="error" role="alert">
            {state.error}
          </Callout>
        )}
        {state?.connected ? (
          <>
            <dl className="facts">
              <div>
                <dt>Conta</dt>
                <dd>{state.email || "Conta Google"}</dd>
              </div>
              <div>
                <dt>Eventos na agenda</dt>
                <dd>{state.events}</dd>
              </div>
              <div>
                <dt>Última sincronização</dt>
                <dd>
                  {state.last_sync
                    ? new Date(state.last_sync).toLocaleString("pt-BR", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : "Ainda não houve"}
                </dd>
              </div>
            </dl>
            <div className="button-row">
              <button
                className="primary"
                disabled={disabled}
                onClick={() =>
                  void run(async () => {
                    await api("/calendar/sync", "POST");
                    m.setNotice("Agenda sincronizada.");
                  })
                }
              >
                Sincronizar agora
              </button>
              {confirming ? (
                <>
                  <button
                    className="danger"
                    disabled={disabled}
                    onClick={() =>
                      void run(async () => {
                        await api("/calendar", "DELETE");
                        setConfirming(false);
                        m.setNotice(
                          "Agenda desconectada. Os eventos já criados continuam nela.",
                        );
                      })
                    }
                  >
                    Confirmar desconexão
                  </button>
                  <button onClick={() => setConfirming(false)}>Cancelar</button>
                </>
              ) : (
                <button disabled={disabled} onClick={() => setConfirming(true)}>
                  Desconectar
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <p>
              O Google exige uma credencial sua, criada uma única vez: no
              Google Cloud, ative a API Google Calendar e crie um ID do cliente
              OAuth do tipo “App para computador”. O passo a passo está em
              docs/AGENDA-GOOGLE.md.
            </p>
            <label className="field">
              ID do cliente
              <input
                value={clientId}
                placeholder="…apps.googleusercontent.com"
                onChange={(e) => setClientId(e.target.value.trim())}
                disabled={disabled}
              />
            </label>
            <label className="field">
              Chave secreta do cliente
              <input
                type="password"
                value={secret}
                autoComplete="off"
                placeholder={
                  state?.configured ? "Guardada no Windows" : undefined
                }
                onChange={(e) => setSecret(e.target.value)}
                disabled={disabled}
              />
            </label>
            <div className="button-row">
              <button
                className="primary"
                disabled={
                  disabled ||
                  waiting ||
                  !(secret ? clientId : state?.configured)
                }
                onClick={() =>
                  void run(async () => {
                    if (secret)
                      await api("/calendar/client", "PUT", {
                        client_id: clientId,
                        client_secret: secret,
                      });
                    setSecret("");
                    await api("/calendar/connect", "POST");
                    setWaiting(true);
                  })
                }
              >
                {waiting ? "Aguardando o Google…" : "Conectar conta Google"}
              </button>
              {waiting && (
                <button onClick={() => setWaiting(false)}>Cancelar</button>
              )}
            </div>
            {waiting && (
              <p role="status" className="small">
                Conclua a autorização na janela do navegador que se abriu.
              </p>
            )}
            <button
              className="link"
              style={{ justifySelf: "start" }}
              onClick={() => openExternal(GOOGLE_CONSOLE)}
            >
              Abrir credenciais do Google Cloud
              <ArrowUpRight size={14} />
            </button>
          </>
        )}
      </div>
    </Panel>
  );
}

function LocalAi({ m }: { m: Monitor }) {
  const [model, setModel] = useState(m.settings.model);
  const [download, setDownload] = useState("");
  const [pulling, setPulling] = useState(false);
  useEffect(() => setModel(m.settings.model), [m.settings.model]);
  const installed = !!m.ollama?.models.includes(m.settings.model);
  const check = () => api<Ollama>("/ollama").then(m.setOllama).catch(m.fail);
  return (
    <Panel
      title="IA local"
      action={
        <span
          className={`badge ${m.ollama?.available ? (installed ? "success" : "warning") : ""}`}
        >
          {m.ollama?.available
            ? installed
              ? "Pronta"
              : "Modelo não baixado"
            : "Ollama não detectado"}
        </span>
      }
    >
      <div className="panel-body">
        <p>
          A análise roda neste computador pelo Ollama. Sem ele, as regras
          continuam triando os e-mails e as mensagens aguardam na fila.
        </p>
        <label className="field">
          Modelo
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={!m.connected}
          />
        </label>
        <div className="button-row">
          <button
            className="primary"
            disabled={!m.connected || model === m.settings.model}
            onClick={() =>
              api<AppSettings>("/settings", "PUT", { model })
                .then((saved) => {
                  m.setSettings(saved);
                  m.setNotice("Modelo salvo.");
                })
                .catch(m.fail)
            }
          >
            Salvar modelo
          </button>
          <button
            disabled={!m.connected || !m.ollama?.available || pulling}
            onClick={async () => {
              setPulling(true);
              try {
                await pullModel(model, setDownload);
                m.setNotice("Download concluído.");
                await check();
              } catch (e) {
                m.fail(e);
              } finally {
                setPulling(false);
              }
            }}
          >
            <ArrowDownToLine size={16} />
            {pulling ? "Baixando…" : "Baixar modelo"}
          </button>
          <button disabled={!m.connected} onClick={() => void check()}>
            Verificar novamente
          </button>
        </div>
        {download && (
          <p role="status" className="small">
            {download}
          </p>
        )}
        <button
          className="link"
          style={{ justifySelf: "start" }}
          onClick={() =>
            isTauri()
              ? void openUrl(OLLAMA_URL)
              : window.open(OLLAMA_URL, "_blank", "noopener")
          }
        >
          Instalar o Ollama pelo site oficial
          <ArrowUpRight size={14} />
        </button>
      </div>
    </Panel>
  );
}

function Application({ version }: { version: string }) {
  const [autostart, setAutostart] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!isTauri()) return;
    import("@tauri-apps/plugin-autostart")
      .then((plugin) => plugin.isEnabled())
      .then(setAutostart)
      .catch(() => {});
  }, []);
  return (
    <Panel title="Aplicativo" className="wide">
      <div className="panel-body">
        <label className="check">
          <input
            type="checkbox"
            checked={autostart}
            disabled={!isTauri()}
            onChange={async (e) => {
              const enable = e.target.checked;
              try {
                const plugin = await import("@tauri-apps/plugin-autostart");
                await (enable ? plugin.enable() : plugin.disable());
                setAutostart(enable);
                setFailed(false);
              } catch {
                setFailed(true);
              }
            }}
          />
          Iniciar com o Windows
        </label>
        {failed && (
          <p role="alert">Não foi possível alterar a inicialização.</p>
        )}
        <p>
          Fechar a janela mantém o Monitor na bandeja, coletando e-mails. Use
          “Sair” no menu da bandeja para encerrar.
        </p>
        <hr />
        <Updates version={version} />
        <hr />
        <h3>Próximas integrações</h3>
        {[
          "Monitor externo e testes dos formulários",
          "Catálogo de arquivos do OneDrive",
          "WhatsApp e mensagens do Instagram",
        ].map((name) => (
          <div className="split" key={name}>
            <span>{name}</span>
            {soon}
          </div>
        ))}
      </div>
    </Panel>
  );
}
