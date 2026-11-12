import { Download, RefreshCw, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { api, Preferences } from "../api";
import { defaultPrefs, type Monitor } from "../store";
import { applyTheme, presets, primaryOk, valid } from "../theme";
import { Avatar, Callout, defaultFronts, FrontIcon, Panel } from "../ui";

/** Normaliza o favicon em PNG transparente; também lê arquivos ICO pelo navegador. */
async function favicon(file: File): Promise<string> {
  if (file.size > 5_000_000) throw new Error("Escolha um ícone de até 5 MB.");
  const allowed = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
  ];
  if (
    !allowed.includes(file.type) &&
    !(
      /\.ico$/i.test(file.name) &&
      ["", "application/octet-stream"].includes(file.type)
    )
  ) {
    throw new Error("Use um arquivo PNG, JPG, WebP ou ICO.");
  }
  // data: é permitido pela política de imagens do desktop; blob: não é.
  const source = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      typeof reader.result === "string"
        ? resolve(reader.result)
        : reject(new Error("Não foi possível ler o ícone."));
    reader.onerror = () => reject(new Error("Não foi possível ler o ícone."));
    reader.readAsDataURL(file);
  });
  const image = new Image();
  image.src = source;
  try {
    await image.decode();
  } catch {
    throw new Error(
      "Não foi possível ler este ícone. Use PNG, JPG, WebP ou ICO.",
    );
  }
  if (!image.naturalWidth || !image.naturalHeight)
    throw new Error("Imagem vazia.");
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const scale = 64 / Math.max(image.naturalWidth, image.naturalHeight);
  const width = image.naturalWidth * scale,
    height = image.naturalHeight * scale;
  canvas
    .getContext("2d")!
    .drawImage(image, (64 - width) / 2, (64 - height) / 2, width, height);
  return canvas.toDataURL("image/png");
}

/** Reduz a foto para 128 px e devolve como data URI. */
async function shrink(file: File): Promise<string> {
  const image = await createImageBitmap(file);
  const side = Math.min(image.width, image.height);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  canvas
    .getContext("2d")!
    .drawImage(
      image,
      (image.width - side) / 2,
      (image.height - side) / 2,
      side,
      side,
      0,
      0,
      128,
      128,
    );
  return canvas.toDataURL("image/jpeg", 0.86);
}

export function Personalization({ m }: { m: Monitor }) {
  const [draft, setDraft] = useState<Preferences>(m.prefs);
  const [saving, setSaving] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const iconPickers = useRef<(HTMLInputElement | null)[]>([]);
  const [iconBusy, setIconBusy] = useState<number | null>(null);
  const saved = useRef(m.prefs);
  useEffect(() => {
    saved.current = m.prefs;
    setDraft(m.prefs);
  }, [m.prefs]);
  // As cores mudam na tela enquanto você escolhe; ao sair sem salvar, voltam.
  useEffect(() => {
    applyTheme(draft, false);
  }, [draft.primary, draft.accent]);
  useEffect(() => () => applyTheme(saved.current, false), []);

  const set = (values: Partial<Preferences>) =>
    setDraft((old) => ({ ...old, ...values }));
  const colorOk = primaryOk(draft.primary) && valid(draft.accent);
  const complete =
    draft.name.trim() && draft.fronts.every((name) => name.trim()) && colorOk;
  const changed = JSON.stringify(draft) !== JSON.stringify(m.prefs);
  const locked = !m.connected;

  async function save() {
    setSaving(true);
    try {
      await m.savePrefs(draft);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Panel title="Personalização" className="wide">
      <div className="panel-body personal">
        <section>
          <h3>Perfil</h3>
          <div className="profile-edit">
            <Avatar src={draft.avatar} name={draft.name} size="lg" />
            <div className="button-row">
              <button
                className="sm"
                disabled={locked}
                onClick={() => picker.current?.click()}
              >
                <Upload size={16} />
                Trocar foto
              </button>
              {draft.avatar && (
                <button
                  className="sm ghost"
                  disabled={locked}
                  onClick={() => set({ avatar: "" })}
                >
                  Remover foto
                </button>
              )}
              <input
                ref={picker}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (!file) return;
                  try {
                    set({ avatar: await shrink(file) });
                  } catch {
                    m.setError("Não foi possível ler esta imagem.");
                  }
                }}
              />
            </div>
          </div>
          <label className="field">
            Nome
            <input
              value={draft.name}
              maxLength={40}
              disabled={locked}
              onChange={(e) => set({ name: e.target.value })}
            />
          </label>
          <label className="field">
            Descrição
            <input
              value={draft.tagline}
              maxLength={60}
              disabled={locked}
              onChange={(e) => set({ tagline: e.target.value })}
            />
          </label>
        </section>
        <section>
          <h3>Frentes</h3>
          <p>
            Nomes e ícones das empresas. Envie um favicon PNG, JPG, WebP ou ICO
            para aparecer antes do nome em todas as abas de filtro. Até 5 MB; o
            ícone é ajustado sem cortar a imagem e mantém a transparência.
          </p>
          {draft.fronts.map((name, i) => (
            <div className="front-editor" key={i}>
              <FrontIcon src={draft.front_icons[i]} name={name} large />
              <label className="field">
                Frente {i + 1}
                <input
                  value={name}
                  maxLength={30}
                  disabled={locked}
                  onChange={(e) =>
                    set({
                      fronts: draft.fronts.map((old, j) =>
                        j === i ? e.target.value : old,
                      ),
                    })
                  }
                />
              </label>
              <div className="button-row">
                <button
                  className="sm"
                  disabled={locked || saving || iconBusy !== null}
                  aria-label={`Enviar ícone da frente ${i + 1}`}
                  onClick={() => iconPickers.current[i]?.click()}
                >
                  <Upload size={16} />
                  {iconBusy === i
                    ? "Preparando…"
                    : draft.front_icons[i]
                      ? "Trocar ícone"
                      : "Enviar ícone"}
                </button>
                {draft.front_icons[i] && (
                  <button
                    className="sm ghost"
                    disabled={locked || saving || iconBusy !== null}
                    aria-label={`Remover ícone da frente ${i + 1}`}
                    onClick={() =>
                      set({
                        front_icons: draft.front_icons.map((icon, j) =>
                          j === i ? "" : icon,
                        ),
                      })
                    }
                  >
                    Remover
                  </button>
                )}
                <input
                  ref={(element) => {
                    iconPickers.current[i] = element;
                  }}
                  type="file"
                  hidden
                  aria-label={`Arquivo do ícone da frente ${i + 1}`}
                  accept="image/png,image/jpeg,image/webp,image/x-icon,image/vnd.microsoft.icon,.ico"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    setIconBusy(i);
                    try {
                      const icon = await favicon(file);
                      set({
                        front_icons: draft.front_icons.map((old, j) =>
                          j === i ? icon : old,
                        ),
                      });
                    } catch (error) {
                      m.setError(
                        error instanceof Error
                          ? error.message
                          : "Não foi possível ler este ícone.",
                      );
                    } finally {
                      setIconBusy(null);
                    }
                  }}
                />
              </div>
            </div>
          ))}
        </section>
        <section>
          <h3>Cores</h3>
          <div className="swatches" role="group" aria-label="Combinações">
            {presets.map((preset) => (
              <button
                key={preset.name}
                className="swatch"
                aria-pressed={
                  draft.primary.toUpperCase() === preset.primary &&
                  draft.accent.toUpperCase() === preset.accent
                }
                disabled={locked}
                onClick={() =>
                  set({ primary: preset.primary, accent: preset.accent })
                }
              >
                <span aria-hidden style={{ background: preset.primary }}>
                  <i style={{ background: preset.accent }} />
                </span>
                {preset.name}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <label className="field">
              Cor principal
              <input
                type="color"
                value={draft.primary}
                disabled={locked}
                onChange={(e) => set({ primary: e.target.value.toUpperCase() })}
              />
            </label>
            <label className="field">
              Cor de destaque
              <input
                type="color"
                value={draft.accent}
                disabled={locked}
                onChange={(e) => set({ accent: e.target.value.toUpperCase() })}
              />
            </label>
          </div>
          {!primaryOk(draft.primary) && (
            <Callout tone="error" role="alert">
              Escolha uma cor principal mais escura. Ela também é a cor do texto
              e precisa continuar legível.
            </Callout>
          )}
          <p>
            A cor principal pinta o menu, os botões e o texto. A de destaque
            aparece só em detalhes, como a marca e o item ativo.
          </p>
        </section>
        <div className="button-row personal-actions">
          <button
            className="primary"
            disabled={
              locked || saving || iconBusy !== null || !changed || !complete
            }
            onClick={() => void save()}
          >
            Salvar personalização
          </button>
          <button
            disabled={locked || saving || iconBusy !== null}
            onClick={() =>
              set({
                fronts: [...defaultFronts],
                primary: defaultPrefs.primary,
                accent: defaultPrefs.accent,
              })
            }
          >
            Restaurar frentes e cores padrão
          </button>
        </div>
      </div>
    </Panel>
  );
}

type UpdateHandle = {
  version: string;
  body?: string;
  downloadAndInstall: (
    onEvent: (event: {
      event: string;
      data?: { contentLength?: number; chunkLength?: number };
    }) => void,
  ) => Promise<void>;
};

export function Updates({ version }: { version: string }) {
  const [state, setState] = useState<
    "idle" | "checking" | "current" | "available" | "installing" | "error"
  >("idle");
  const [progress, setProgress] = useState("");
  const [message, setMessage] = useState("");
  const update = useRef<UpdateHandle | null>(null);
  const desktop = isTauri();
  const [nativeVersion, setNativeVersion] = useState<string | null>(null);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    getVersion()
      .then((value) => {
        if (active) setNativeVersion(typeof value === "string" ? value : "");
      })
      .catch(() => {
        if (active) setNativeVersion("");
      });
    return () => {
      active = false;
    };
  }, [desktop]);

  async function check() {
    setState("checking");
    setMessage("");
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const found = (await check()) as UpdateHandle | null;
      update.current = found;
      setState(found ? "available" : "current");
    } catch {
      setState("error");
      setMessage(
        "Não foi possível consultar as atualizações. Verifique a internet e tente de novo.",
      );
    }
  }
  async function install() {
    if (!update.current) return;
    setState("installing");
    let total = 0,
      received = 0;
    try {
      await update.current.downloadAndInstall((event) => {
        if (event.event === "Started") total = event.data?.contentLength ?? 0;
        if (event.event === "Progress") {
          received += event.data?.chunkLength ?? 0;
          setProgress(
            total
              ? `Baixando… ${Math.round((received / total) * 100)}%`
              : "Baixando…",
          );
        }
        if (event.event === "Finished") setProgress("Instalando…");
      });
    } catch {
      setState("error");
      setMessage(
        "A atualização não pôde ser instalada. Nada foi alterado; tente de novo.",
      );
    }
  }
  return (
    <div className="updates">
      <div className="split">
        <span>
          <strong>Monitor</strong>
          <small>
            {desktop
              ? `Versão instalada: ${nativeVersion || version || (nativeVersion === null ? "Carregando…" : "Não identificada")}`
              : "Prévia no navegador · abra o aplicativo para consultar a versão instalada"}
            {state === "current" && " · você já tem a mais recente"}
            {state === "available" &&
              ` · versão ${update.current?.version} disponível`}
          </small>
        </span>
        <div className="button-row">
          <button
            disabled={
              !desktop || state === "checking" || state === "installing"
            }
            onClick={() => void check()}
          >
            <RefreshCw size={16} />
            {state === "checking" ? "Verificando…" : "Verificar atualizações"}
          </button>
          {(state === "available" || state === "installing") && (
            <button
              className="primary"
              disabled={state === "installing"}
              onClick={() => void install()}
            >
              <Download size={16} />
              {state === "installing"
                ? progress || "Preparando…"
                : "Atualizar agora"}
            </button>
          )}
        </div>
      </div>
      {state === "available" && (
        <p>
          O Monitor baixa a nova versão, fecha, instala e abre de novo. Seus
          dados e a pasta de arquivos são mantidos.
        </p>
      )}
      {message && <p role="alert">{message}</p>}
    </div>
  );
}
