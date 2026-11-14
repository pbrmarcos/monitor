import { useEffect, useId, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import type { DraftBundle } from "../api";

export function DraftMessages({ bundle }: { bundle: DraftBundle }) {
  const id = useId();
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState<number | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  async function copy(index: number) {
    setError("");
    try {
      await navigator.clipboard.writeText(bundle.items[index].text);
      setCopied(index);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setError(
        "Não foi possível copiar. Selecione o texto da mensagem para copiar manualmente.",
      );
    }
  }
  const copyButton = (index: number) => (
    <button
      className="sm"
      aria-label={`Copiar ${bundle.items[index].label}`}
      onClick={() => void copy(index)}
    >
      {copied === index ? (
        <Check size={16} aria-hidden />
      ) : (
        <Copy size={16} aria-hidden />
      )}
      {copied === index ? "Copiado" : "Copiar"}
    </button>
  );
  return (
    <div className="draft-bundle">
      {bundle.method === "guided" && (
        <p className="draft-intro">
          Organizadas a partir das pendências da conversa. Confira os dados
          antes de enviar.
        </p>
      )}
      <p className="draft-intro">
        {bundle.kind === "sequence"
          ? `Sequência de ${bundle.items.length} mensagens`
          : `${bundle.items.length} versões · escolha uma`}
      </p>
      {bundle.kind === "alternatives" ? (
        <>
          <div
            className="draft-tabs"
            role="tablist"
            aria-label="Tons das mensagens"
          >
            {bundle.items.map((item, index) => (
              <button
                key={index}
                role="tab"
                id={`${id}-tab-${index}`}
                aria-controls={`${id}-panel-${index}`}
                aria-selected={active === index}
                tabIndex={active === index ? 0 : -1}
                className="sm"
                onClick={() => setActive(index)}
                onKeyDown={(event) => {
                  const next =
                    event.key === "ArrowRight"
                      ? (index + 1) % bundle.items.length
                      : event.key === "ArrowLeft"
                        ? (index + bundle.items.length - 1) %
                          bundle.items.length
                        : event.key === "Home"
                          ? 0
                          : event.key === "End"
                            ? bundle.items.length - 1
                            : null;
                  if (next !== null) {
                    event.preventDefault();
                    setActive(next);
                    document.getElementById(`${id}-tab-${next}`)?.focus();
                  }
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id={`${id}-panel-${active}`}
            aria-labelledby={`${id}-tab-${active}`}
          >
            <div className="draft-body">{bundle.items[active].text}</div>
            <div className="draft-copy">{copyButton(active)}</div>
          </div>
        </>
      ) : (
        <ol className="draft-sequence">
          {bundle.items.map((item, index) => (
            <li key={index}>
              <div className="split">
                <strong>{item.label}</strong>
                {copyButton(index)}
              </div>
              <div className="draft-body">{item.text}</div>
            </li>
          ))}
        </ol>
      )}
      {error && (
        <p role="alert" className="small">
          {error}
        </p>
      )}
    </div>
  );
}
