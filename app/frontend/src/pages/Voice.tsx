import { Download, Mic, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, VoiceStatus } from "../api";
import type { Monitor } from "../store";
import { Callout, Panel } from "../ui";

/** Modelo de voz local: o áudio do microfone é transcrito neste computador. */
export function VoicePanel({ m }: { m: Monitor }) {
  const [state, setState] = useState<VoiceStatus | null>(null);
  const [confirming, setConfirming] = useState(false);
  const { connected, fail } = m;
  const refresh = () =>
    api<VoiceStatus>("/voice").then((value) => {
      setState(value);
      return value;
    });
  useEffect(() => {
    if (connected) void refresh().catch(() => {});
  }, [connected]);
  // Enquanto o modelo baixa, acompanha o progresso a cada segundo e meio.
  const downloading = !!state?.downloading;
  useEffect(() => {
    if (!downloading) return;
    const timer = setInterval(() => void refresh().catch(() => {}), 1500);
    return () => clearInterval(timer);
  }, [downloading]);

  const choice = state?.sizes.find((item) => item.id === state.size);
  const act = (action: () => Promise<unknown>) =>
    action().then(refresh).catch(fail);
  const disabled = !connected || m.preview;
  return (
    <Panel
      title="Voz e microfone"
      action={
        <span className={`badge ${state?.ready ? "success" : ""}`}>
          {!state
            ? "—"
            : !state.engine
              ? "Motor ausente"
              : state.ready
                ? "Pronto"
                : state.downloading
                  ? `Baixando ${Math.round(state.progress * 100)}%`
                  : "Modelo não baixado"}
        </span>
      }
    >
      <div className="panel-body">
        <p>
          O botão de microfone do assistente grava a sua voz e transcreve neste
          computador, com um modelo Whisper. O áudio não é enviado a nenhum
          serviço e não fica guardado. O modelo é baixado uma vez, do
          repositório público Systran/faster-whisper no Hugging Face, e
          conferido por assinatura SHA-256.
        </p>
        {state && !state.engine && (
          <Callout tone="error" role="alert">
            O motor de voz não está incluído nesta instalação do Monitor.
          </Callout>
        )}
        <label className="field">
          Qualidade da transcrição
          <select
            value={state?.size ?? "small"}
            disabled={disabled || !state || downloading}
            onChange={(event) =>
              void act(() =>
                api("/voice", "PUT", { size: event.target.value }),
              )
            }
          >
            {state?.sizes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label} · download de {item.mb} MB
              </option>
            ))}
          </select>
        </label>
        {downloading && (
          <progress
            max={1}
            value={state?.progress ?? 0}
            aria-label="Progresso do download"
          />
        )}
        {state?.error && (
          <Callout tone="error" role="alert">
            {state.error}
          </Callout>
        )}
        <div className="button-row">
          <button
            className="primary"
            disabled={disabled || !state?.engine || state.ready || downloading}
            onClick={() => void act(() => api("/voice/download", "POST"))}
          >
            <Download size={16} />
            {downloading
              ? "Baixando…"
              : `Baixar modelo${choice ? ` (${choice.mb} MB)` : ""}`}
          </button>
          {state?.ready &&
            (confirming ? (
              <>
                <button
                  className="danger"
                  onClick={() => {
                    setConfirming(false);
                    void act(() => api("/voice", "DELETE"));
                  }}
                >
                  Confirmar remoção
                </button>
                <button onClick={() => setConfirming(false)}>Cancelar</button>
              </>
            ) : (
              <button disabled={disabled} onClick={() => setConfirming(true)}>
                <Trash2 size={16} />
                Remover modelo
              </button>
            ))}
        </div>
        <p className="small">
          <Mic size={14} aria-hidden /> Na primeira gravação o Windows pode
          pedir permissão para o microfone. Se negar sem querer, libere em
          Configurações do Windows › Privacidade e segurança › Microfone.
        </p>
      </div>
    </Panel>
  );
}
