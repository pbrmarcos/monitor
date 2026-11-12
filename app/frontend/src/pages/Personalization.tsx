import { Download, RefreshCw, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { api, Preferences } from "../api";
import { defaultPrefs, type Monitor } from "../store";
import { applyTheme, presets, primaryOk, valid } from "../theme";
import { Avatar, Callout, defaultFronts, Panel } from "../ui";

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
            O nome de cada empresa ou projeto. Aparece nos filtros, nas
            demandas, nos e-mails e nos eventos da agenda.
          </p>
          {draft.fronts.map((name, i) => (
            <label className="field" key={i}>
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
              Escolha uma cor principal mais escura. Ela também é a cor do
              texto e precisa continuar legível.
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
            disabled={locked || saving || !changed || !complete}
            onClick={() => void save()}
          >
            Salvar personalização
          </button>
          <button
            disabled={locked || saving}
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
          <strong>Atualizações</strong>
          <small>
            Versão instalada: {version || "—"}
            {state === "current" && " · você já tem a mais recente"}
            {state === "available" &&
              ` · versão ${update.current?.version} disponível`}
          </small>
        </span>
        <div className="button-row">
          {state === "available" || state === "installing" ? (
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
          ) : (
            <button
              disabled={!desktop || state === "checking"}
              onClick={() => void check()}
            >
              <RefreshCw size={16} />
              {state === "checking" ? "Verificando…" : "Verificar atualizações"}
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
