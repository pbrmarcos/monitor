import { useCallback, useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  Account,
  api,
  AppSettings,
  connect,
  Demand,
  Email,
  Importance,
  Ollama,
  Preferences,
  SocialProfile,
  Storage,
  Suggestion,
} from "./api";
import {
  demoDemands,
  demoEmails,
  demoSocial,
  demoSuggestions,
  today,
} from "./demo";
import { applyTheme, defaultTheme } from "./theme";
import { defaultFronts, setFrontNames } from "./ui";

export const pages = [
  "Visão geral",
  "Demandas",
  "Lembretes",
  "E-mails",
  "Sites",
  "Redes sociais",
  "Arquivos",
  "Assistente",
  "Configurações",
] as const;
export type Page = (typeof pages)[number];
export type HistoryEvent = {
  id: number;
  description: string;
  created_at: string;
};

export const defaultPrefs: Preferences = {
  name: "Marcos",
  tagline: "Seu espaço pessoal",
  avatar: "",
  fronts: defaultFronts,
  front_icons: ["", "", "", ""],
  ...defaultTheme,
};

export const newDemand = (): Omit<Demand, "id"> => ({
  title: "",
  front_id: 1,
  contact: "",
  channel: "manual",
  stage: "novo",
  priority: "normal",
  due: null,
  next_action: "",
  return_date: null,
  summary: "",
  origin_ref: "",
});
export const isClosed = (d: Demand) => ["ganho", "perdido"].includes(d.stage);

export function useMonitor() {
  const [page, setPage] = useState<Page>("Visão geral");
  const [front, setFront] = useState(0);
  const [query, setQuery] = useState("");
  const [connected, setConnected] = useState(false);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [demands, setDemands] = useState<Demand[]>([]);
  const [emails, setEmails] = useState<Email[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [pendingAi, setPendingAi] = useState(0);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [ollama, setOllama] = useState<Ollama | null>(null);
  const [settings, setSettings] = useState<AppSettings>({
    model: "qwen3.5:4b-q4_K_M",
    priority_senders: [],
  });
  const [editing, setEditing] = useState<Partial<Demand> | null>(null);
  const [detail, setDetail] = useState<Demand | null>(null);
  const [reminderTarget, setReminderTarget] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);
  const [social, setSocial] = useState<SocialProfile[]>([]);
  const [version, setVersion] = useState("");
  const usePrefs = (value: Preferences) => {
    setFrontNames(value.fronts);
    applyTheme(value);
    setPrefs({ ...value, front_icons: value.front_icons ?? ["", "", "", ""] });
  };

  const fail = (e: unknown) => setError((e as Error).message);

  const refreshInbox = useCallback(async () => {
    const [mail, suggested, list, queue] = await Promise.all([
      api<Email[]>("/emails"),
      api<Suggestion[]>("/suggestions"),
      api<Account[]>("/email-accounts"),
      api<{ pending: number }>("/ai/status"),
    ]);
    setEmails(mail);
    setSuggestions(suggested);
    setAccounts(list);
    setPendingAi(queue.pending);
  }, []);
  const refreshDemands = useCallback(
    async () => setDemands(await api<Demand[]>("/demands")),
    [],
  );

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      await connect();
      const health = await api<{ demo: boolean; version: string }>("/health");
      setPreview(health.demo);
      setVersion(health.version);
      usePrefs(await api<Preferences>("/preferences"));
      setDemands(await api<Demand[]>("/demands"));
      setConnected(true);
      const [saved, local, folder] = await Promise.all([
        api<AppSettings>("/settings"),
        api<Ollama>("/ollama"),
        api<Storage>("/storage"),
        refreshInbox(),
      ]);
      setSocial(
        health.demo ? demoSocial : await api<SocialProfile[]>("/social"),
      );
      setSettings(saved);
      setOllama(local);
      setStorage(folder);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }, [refreshInbox]);

  useEffect(() => {
    void load();
    const disposers: (() => void)[] = [];
    let disposed = false;
    const keep = (fn: () => void) => (disposed ? fn() : disposers.push(fn));
    if (isTauri()) {
      listen<string>("navigate", (event) => {
        if (event.payload === "new") setEditing(newDemand());
        else setPage("Visão geral");
      }).then(keep);
      listen("backend-ready", () => void load()).then(keep);
      listen<{ id: number | null; demand_id: number | null }>(
        "notification-open",
        (event) => {
          setPage("Lembretes");
          setFront(0);
          if (event.payload.id)
            void api(`/notifications/${event.payload.id}/read`, "POST").catch(
              () => {},
            );
          if (event.payload.demand_id)
            void api<Demand[]>("/demands")
              .then((items) => {
                setDemands(items);
                const demand = items.find(
                  (d) => d.id === event.payload.demand_id,
                );
                if (demand) setDetail(demand);
              })
              .catch(() => {});
        },
      ).then(keep);
    }
    return () => {
      disposed = true;
      disposers.forEach((fn) => fn());
    };
  }, [load]);

  useEffect(() => {
    if (!connected) return;
    const timer = setInterval(() => void refreshInbox().catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, [connected, refreshInbox]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  function startDemo() {
    setDemands(demoDemands);
    setEmails(demoEmails);
    setSuggestions(demoSuggestions);
    setSocial(demoSocial);
    setPreview(true);
    setError("");
  }

  async function saveDemand(value: Partial<Demand>) {
    setSaving(true);
    try {
      const payload = { ...newDemand(), ...value };
      if (!connected && payload.stage === "acompanhar" && !payload.return_date)
        throw new Error("Informe uma data de retorno.");
      const item = connected
        ? await api<Demand>(
            value.id ? `/demands/${value.id}` : "/demands",
            value.id ? "PUT" : "POST",
            payload,
          )
        : ({ ...payload, id: value.id || Date.now() } as Demand);
      setDemands((old) =>
        value.id
          ? old.map((d) => (d.id === item.id ? item : d))
          : [item, ...old],
      );
      const origin = Number(payload.origin_ref?.split(":")[1]);
      if (origin && !value.id) {
        setEmails((old) =>
          old.map((e) =>
            e.id === origin
              ? { ...e, demand_id: item.id, suggestion_id: null }
              : e,
          ),
        );
        setSuggestions((old) => old.filter((s) => s.email_id !== origin));
      }
      setEditing(null);
      setDetail(null);
      setError("");
      setNotice(value.id ? "Demanda atualizada." : "Demanda criada.");
    } catch (e) {
      fail(e);
    } finally {
      setSaving(false);
    }
  }

  async function savePrefs(value: Preferences) {
    try {
      usePrefs(await api<Preferences>("/preferences", "PUT", value));
      setNotice("Personalização salva.");
    } catch (e) {
      fail(e);
    }
  }

  async function removeDemand(d: Demand) {
    try {
      if (connected) await api(`/demands/${d.id}`, "DELETE");
      setDemands((old) => old.filter((item) => item.id !== d.id));
      setDetail(null);
      setNotice("Demanda excluída.");
      if (connected) void refreshInbox().catch(() => {});
    } catch (e) {
      fail(e);
    }
  }

  function moveDemand(d: Demand, stage: string) {
    if (stage === "acompanhar" && !d.return_date) {
      setEditing({ ...d, stage });
      return;
    }
    void saveDemand({ ...d, stage });
  }

  function emailToDemand(e: Email) {
    setEditing({
      ...newDemand(),
      front_id: e.front_id,
      title: e.analysis?.acao_sugerida || e.subject,
      channel: "email",
      contact: e.sender.slice(0, 200),
      summary: e.analysis?.resumo || e.body.slice(0, 600),
      due: e.analysis?.prazo_iso || null,
      origin_ref: `email:${e.id}`,
    });
  }

  async function correctEmail(
    e: Email,
    value: "importante" | "nao_importante",
  ) {
    try {
      const current = e.analysis?.importancia ?? "revisar";
      const importance: Importance = connected
        ? (
            await api<{ importancia: Importance }>(
              `/emails/${e.id}/correction`,
              "POST",
              { value },
            )
          ).importancia
        : value === "nao_importante"
          ? "info"
          : current === "acao"
            ? "acao"
            : "importante";
      setEmails((old) =>
        old.map((item) =>
          item.id === e.id && item.analysis
            ? {
                ...item,
                suggestion_id:
                  value === "nao_importante" ? null : item.suggestion_id,
                analysis: {
                  ...item.analysis,
                  importancia: importance,
                  correcao: value,
                },
              }
            : item,
        ),
      );
      if (value === "nao_importante")
        setSuggestions((old) => old.filter((s) => s.email_id !== e.id));
      setNotice("Correção salva. Ela orienta as próximas análises.");
    } catch (err) {
      fail(err);
    }
  }

  async function acceptSuggestion(s: Suggestion) {
    try {
      const item = connected
        ? await api<Demand>(`/suggestions/${s.id}/accept`, "POST")
        : ({
            ...newDemand(),
            id: Date.now(),
            title: s.title,
            front_id: s.front_id,
            contact: s.contact,
            channel: "email",
            summary: s.summary,
            due: s.due,
          } as Demand);
      setDemands((old) => [item, ...old]);
      setSuggestions((old) => old.filter((x) => x.id !== s.id));
      setEmails((old) =>
        old.map((e) =>
          e.id === s.email_id
            ? { ...e, demand_id: item.id, suggestion_id: null }
            : e,
        ),
      );
      setNotice("Demanda criada.");
    } catch (e) {
      fail(e);
    }
  }

  async function dismissSuggestion(s: Suggestion) {
    try {
      if (connected) await api(`/suggestions/${s.id}/dismiss`, "POST");
      setSuggestions((old) => old.filter((x) => x.id !== s.id));
      setEmails((old) =>
        old.map((e) =>
          e.id === s.email_id ? { ...e, suggestion_id: null } : e,
        ),
      );
    } catch (e) {
      fail(e);
    }
  }

  const matches = (text: string) =>
    text.toLowerCase().includes(query.toLowerCase());
  const visible = demands.filter(
    (d) =>
      (!front || d.front_id === front) && matches(`${d.title} ${d.contact}`),
  );
  const open = visible.filter((d) => !isClosed(d));
  const dueToday = open.filter(
    (d) =>
      (d.due && d.due <= today()) ||
      (d.return_date && d.return_date <= today()),
  );
  const inbox = emails.filter((e) => !front || e.front_id === front);
  const suggested = suggestions.filter((s) => !front || s.front_id === front);

  return {
    page,
    setPage: (value: Page) => {
      setPage(value);
      setQuery("");
    },
    front,
    setFront,
    query,
    setQuery,
    connected,
    preview,
    busy,
    error,
    setError,
    notice,
    setNotice,
    fail,
    load,
    startDemo,
    demands,
    visible,
    open,
    dueToday,
    inbox,
    suggested,
    accounts,
    pendingAi,
    storage,
    setStorage,
    ollama,
    setOllama,
    settings,
    setSettings,
    editing,
    setEditing,
    detail,
    reminderTarget,
    setReminderTarget,
    setDetail,
    saving,
    saveDemand,
    removeDemand,
    moveDemand,
    emailToDemand,
    correctEmail,
    acceptSuggestion,
    dismissSuggestion,
    refreshInbox,
    refreshDemands,
    prefs,
    savePrefs,
    social,
    setSocial,
    version,
  };
}
export type Monitor = ReturnType<typeof useMonitor>;
