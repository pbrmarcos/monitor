import { Copy, PenLine, RefreshCw, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, Email, WritingStyle as Style } from "../api";
import type { Monitor } from "../store";
import { Callout, frontLabel, Panel, senderName } from "../ui";

type Options = { options: string[] };
type Alternatives = { start: number; end: number; options: string[] };

/** Exemplos fixos para a prévia do navegador, onde não há modelo. */
function sampleReplies(email: Email, name: string) {
  const first = senderName(email.sender).split(" ")[0] || "tudo bem";
  return [
    `Olá, ${first}!\n\nRecebi sua mensagem e retorno até [data].\n\nAbraços,\n${name}`,
    `Olá, ${first}!\n\nObrigado pela mensagem. Vou analisar com calma o que você pediu e te retorno até [data] com todos os detalhes.\n\nQualquer coisa, é só me avisar.\n\nAbraços,\n${name}`,
  ];
}
const sampleImprove = (text: string) => {
  const clean = text.trim().replace(/\s+/g, " ");
  const sentence = clean.charAt(0).toUpperCase() + clean.slice(1);
  return [
    sentence.replace(/[.!]*$/, "."),
    `${sentence.replace(/[.!]*$/, "")}, tudo bem?`,
  ];
};

export function ReplyBox({ email, m }: { email: Email; m: Monitor }) {
  const [draft, setDraft] = useState("");
  const [instruction, setInstruction] = useState("");
  const [options, setOptions] = useState<string[] | null>(null);
  const [alternatives, setAlternatives] = useState<Alternatives | null>(null);
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const [busy, setBusy] = useState<"" | "suggest" | "improve">("");
  const saved = useRef("");
  const loaded = useRef(false);
  const online = m.connected;
  const { fail } = m;

  useEffect(() => {
    if (!online) {
      loaded.current = true;
      return;
    }
    let current = true;
    api<{ body: string }>(`/emails/${email.id}/draft`)
      .then((value) => {
        if (!current) return;
        saved.current = value.body;
        loaded.current = true;
        setDraft(value.body);
      })
      .catch(() => {
        loaded.current = true;
      });
    return () => {
      current = false;
    };
  }, [email.id, online]);
  // O rascunho é salvo sozinho, um instante depois de você parar de digitar.
  useEffect(() => {
    if (!online || !loaded.current || draft === saved.current) return;
    const timer = setTimeout(() => {
      api(`/emails/${email.id}/draft`, "PUT", { body: draft })
        .then(() => {
          saved.current = draft;
        })
        .catch(() => {});
    }, 800);
    return () => clearTimeout(timer);
  }, [draft, email.id, online]);

  const write = (text: string) => {
    setDraft(text);
    setAlternatives(null);
  };
  async function suggest() {
    setBusy("suggest");
    try {
      setOptions(
        online
          ? (
              await api<Options>(`/emails/${email.id}/replies`, "POST", {
                instruction,
              })
            ).options
          : sampleReplies(email, m.prefs.name),
      );
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function improve() {
    const { start, end } = selection;
    const text = draft.slice(start, end);
    if (!text.trim()) return;
    setBusy("improve");
    try {
      const result = online
        ? (
            await api<Options>("/emails/improve", "POST", {
              text,
              draft,
              account_id: email.account_id,
            })
          ).options
        : sampleImprove(text);
      setAlternatives({ start, end, options: result });
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  const selected = draft.slice(selection.start, selection.end).trim();
  return (
    <section className="reply" aria-label="Responder">
      <header>
        <h3>
          <PenLine size={18} aria-hidden />
          Responder
        </h3>
        <span className="badge">Rascunho · o Monitor não envia</span>
      </header>
      <label className="field">
        O que você quer dizer? (opcional)
        <input
          value={instruction}
          maxLength={600}
          placeholder="Ex.: aceitar e dizer que entrego na sexta"
          onChange={(e) => setInstruction(e.target.value)}
        />
      </label>
      <div className="button-row">
        <button onClick={() => void suggest()} disabled={busy !== ""}>
          <Sparkles size={16} />
          {busy === "suggest"
            ? "Escrevendo…"
            : options
              ? "Sugerir outras 2"
              : "Sugerir 2 respostas"}
        </button>
      </div>
      {options && (
        <div className="reply-options">
          {options.map((text, i) => (
            <div className="reply-option" key={i}>
              <span className="eyebrow">
                Opção {i + 1} · {i ? "completa" : "direta"}
              </span>
              <p>{text}</p>
              <button
                className="sm"
                onClick={() => {
                  write(text);
                  setOptions(null);
                }}
              >
                Usar opção {i + 1}
              </button>
            </div>
          ))}
        </div>
      )}
      <label className="field">
        Sua resposta
        <textarea
          rows={9}
          maxLength={12000}
          value={draft}
          placeholder="Escreva aqui ou use uma das sugestões. Selecione uma frase ou um parágrafo para melhorar só aquele trecho."
          onChange={(e) => write(e.target.value)}
          onSelect={(e) =>
            setSelection({
              start: e.currentTarget.selectionStart,
              end: e.currentTarget.selectionEnd,
            })
          }
        />
      </label>
      <div className="button-row">
        <button
          onClick={() => void improve()}
          disabled={busy !== "" || !selected}
          title={selected ? undefined : "Selecione um trecho da resposta"}
        >
          <Wand2 size={16} />
          {busy === "improve" ? "Reescrevendo…" : "Melhorar trecho selecionado"}
        </button>
        <button
          disabled={!draft.trim()}
          onClick={() =>
            navigator.clipboard
              .writeText(draft)
              .then(() => m.setNotice("Resposta copiada."))
              .catch(() => m.setError("Não foi possível copiar o texto."))
          }
        >
          <Copy size={16} />
          Copiar resposta
        </button>
      </div>
      {!selected && draft.trim() && !alternatives && (
        <p className="muted caption">
          Para melhorar, selecione com o mouse a frase ou o parágrafo dentro da
          resposta.
        </p>
      )}
      {alternatives && (
        <div className="reply-improve">
          <p className="small">
            <strong>Trecho original:</strong> “
            {draft.slice(alternatives.start, alternatives.end)}”
          </p>
          <div className="reply-options">
            {alternatives.options.map((text, i) => (
              <div className="reply-option" key={i}>
                <span className="eyebrow">
                  Versão {i + 1} · {i ? "cordial" : "direta"}
                </span>
                <p>{text}</p>
                <button
                  className="sm"
                  onClick={() => {
                    write(
                      draft.slice(0, alternatives.start) +
                        text +
                        draft.slice(alternatives.end),
                    );
                    setSelection({ start: 0, end: 0 });
                  }}
                >
                  Usar versão {i + 1}
                </button>
              </div>
            ))}
          </div>
          <button className="link" onClick={() => setAlternatives(null)}>
            Manter o original
          </button>
        </div>
      )}
      <p className="muted caption">
        As sugestões saem da IA local e podem conter erros ou promessas que
        você não fez. Revise, complete os [colchetes] e envie pelo seu programa
        de e-mail.
      </p>
    </section>
  );
}

const sentNote: Record<string, string> = {
  "": "Os enviados desta conta ainda não foram lidos. A leitura acontece a cada 30 minutos ou ao clicar em Reaprender.",
  sem_pasta:
    "Não encontrei a pasta de enviados nesta conta. As respostas usam um tom neutro até você descrever seu estilo abaixo.",
  erro: "A última leitura dos enviados falhou. O Monitor tenta de novo sozinho.",
};

/** Como o usuário escreve em cada conta: aprendido dos enviados e editável. */
export function WritingStyle({ m }: { m: Monitor }) {
  const [styles, setStyles] = useState<Style[]>([]);
  const [texts, setTexts] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(0);
  const { connected, accounts } = m;
  const put = (style: Style) => {
    setStyles((old) =>
      old.map((item) => (item.account_id === style.account_id ? style : item)),
    );
    setTexts((old) => ({ ...old, [style.account_id]: style.profile }));
  };
  useEffect(() => {
    if (!connected) return;
    api<Style[]>("/email-style")
      .then((list) => {
        setStyles(list);
        setTexts(
          Object.fromEntries(list.map((s) => [s.account_id, s.profile])),
        );
      })
      .catch(() => {});
  }, [connected, accounts.length]);
  const run = async (id: number, action: () => Promise<Style>, done: string) => {
    setBusy(id);
    try {
      put(await action());
      m.setNotice(done);
    } catch (e) {
      m.fail(e);
    } finally {
      setBusy(0);
    }
  };
  return (
    <Panel
      title="Seu jeito de escrever"
      className="wide"
      action={<span className="badge ai">IA local</span>}
    >
      <div className="panel-body">
        <p>
          O Monitor lê, sem alterar nada, os últimos 100 e-mails da pasta de
          enviados de cada conta e descreve como você escreve: saudação,
          despedida, tom e tamanho. As sugestões de resposta seguem esse
          perfil. Os textos ficam neste computador e só passam pelo modelo
          local.
        </p>
        {!styles.length && (
          <Callout>
            {connected
              ? "Conecte uma conta de e-mail para o Monitor aprender seu estilo."
              : "Na prévia do navegador não há contas para aprender."}
          </Callout>
        )}
        {styles.map((style) => (
          <div className="style-card" key={style.account_id}>
            <div className="split">
              <span>
                <strong>{style.address}</strong>
                <small>
                  {frontLabel(style.front_id)} · {style.sent} enviado(s)
                  lido(s)
                  {style.edited && " · perfil editado por você"}
                </small>
              </span>
              <button
                className="sm"
                disabled={busy === style.account_id || m.preview}
                onClick={() =>
                  void run(
                    style.account_id,
                    () =>
                      api<Style>(
                        `/email-style/${style.account_id}/learn`,
                        "POST",
                      ),
                    "Estilo atualizado a partir dos seus enviados.",
                  )
                }
              >
                <RefreshCw size={16} />
                {busy === style.account_id ? "Lendo enviados…" : "Reaprender"}
              </button>
            </div>
            {style.sent_status !== "ok" && (
              <p className="muted small">{sentNote[style.sent_status]}</p>
            )}
            {(style.greeting || style.closing || style.words > 0) && (
              <dl className="facts">
                <div>
                  <dt>Saudação mais usada</dt>
                  <dd>{style.greeting || "—"}</dd>
                </div>
                <div>
                  <dt>Despedida mais usada</dt>
                  <dd>{style.closing || "—"}</dd>
                </div>
                <div>
                  <dt>Tamanho habitual</dt>
                  <dd>{style.words ? `${style.words} palavras` : "—"}</dd>
                </div>
              </dl>
            )}
            <label className="field">
              Como você escreve nesta conta
              <textarea
                rows={6}
                maxLength={1500}
                value={texts[style.account_id] ?? ""}
                placeholder="O perfil aparece aqui depois da leitura dos enviados. Você também pode escrever o seu."
                onChange={(e) =>
                  setTexts((old) => ({
                    ...old,
                    [style.account_id]: e.target.value,
                  }))
                }
              />
            </label>
            <div className="button-row">
              <button
                disabled={
                  busy === style.account_id ||
                  (texts[style.account_id] ?? "") === style.profile
                }
                onClick={() =>
                  void run(
                    style.account_id,
                    () =>
                      api<Style>(`/email-style/${style.account_id}`, "PUT", {
                        profile: texts[style.account_id] ?? "",
                      }),
                    "Perfil salvo. As próximas sugestões seguem este texto.",
                  )
                }
              >
                Salvar perfil
              </button>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
