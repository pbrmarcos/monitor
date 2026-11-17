import type { Account, Demand, Email, Suggestion } from "./api";
import type { Site } from "./pages/Sites";

export type PriorityGroup = "agora" | "hoje" | "novidades" | "aguardando";

export const groupLabels: Record<PriorityGroup, string> = {
  agora: "Precisa de você agora",
  hoje: "Para hoje",
  novidades: "Novidades",
  aguardando: "Aguardando terceiros",
};
export const groupOrder: PriorityGroup[] = [
  "agora",
  "hoje",
  "novidades",
  "aguardando",
];

/** O que cada item aponta. O canal é texto livre: WhatsApp e CRM entram como novas fontes. */
export type PriorityRef =
  | { type: "email"; email: Email; suggestion?: Suggestion }
  | { type: "suggestion"; suggestion: Suggestion }
  | { type: "demand"; demand: Demand }
  | { type: "site"; site: Site }
  | { type: "account"; account: Account };

export type PriorityItem = {
  key: string;
  group: PriorityGroup;
  front_id: number;
  channel: string;
  title: string;
  reason: string;
  /** Instante em que o item passou a esperar você (ISO), quando se sabe. */
  since: string | null;
  ref: PriorityRef;
};

export type PriorityInput = {
  demands: Demand[];
  emails: Email[];
  suggestions: Suggestion[];
  accounts: Account[];
  sites: Site[];
  /** Filtro de frente; 0 = todas. */
  front: number;
  today: string;
  now: number;
};

const FOLLOW_UP_STAGES = ["proposta_enviada", "acompanhar"];
const closed = (d: Demand) => ["ganho", "perdido"].includes(d.stage);
const level = (e: Email) => e.analysis?.importancia ?? "revisar";

/** E-mails que esperam decisão: sem demanda ligada e classificados como importantes ou de ação. */
export const awaitingMail = (emails: Email[]) =>
  emails.filter(
    (e) => !e.demand_id && ["acao", "importante"].includes(level(e)),
  );

/** Contagens que toda tela deve usar, para que os números batam entre si. */
export function mailCounts(emails: Email[]) {
  const acao = emails.filter((e) => level(e) === "acao");
  const importante = emails.filter((e) => level(e) === "importante");
  return {
    total: emails.length,
    acao: acao.length,
    importante: importante.length,
    acaoSemDemanda: acao.filter((e) => !e.demand_id).length,
    importanteSemDemanda: importante.filter((e) => !e.demand_id).length,
    comDemanda: emails.filter(
      (e) => e.demand_id && ["acao", "importante"].includes(level(e)),
    ).length,
    revisar: emails.filter((e) => level(e) === "revisar").length,
  };
}

const waitingMs = (item: PriorityItem, now: number) =>
  item.since ? now - Date.parse(item.since) : 0;

export function buildPriorities(input: PriorityInput): PriorityItem[] {
  const inFront = (id: number) => !input.front || id === input.front;
  const items: PriorityItem[] = [];
  const suggestionOf = new Map(input.suggestions.map((s) => [s.email_id, s]));
  const shownEmails = new Set<number>();

  for (const site of input.sites) {
    if (!site.enabled || !inFront(site.front_id)) continue;
    if (site.latest && !site.latest.ok)
      items.push({
        key: `site:${site.id}`,
        group: "agora",
        front_id: site.front_id,
        channel: "site",
        title: `${site.name} está fora do ar`,
        reason: "A última checagem falhou.",
        since: site.latest.checked_at,
        ref: { type: "site", site },
      });
  }
  for (const account of input.accounts) {
    if (account.status !== "erro" || !inFront(account.front_id)) continue;
    items.push({
      key: `account:${account.id}`,
      group: "agora",
      front_id: account.front_id,
      channel: "integração",
      title: `Conta ${account.address} desconectada`,
      reason: account.status_detail || "Não foi possível ler esta caixa.",
      since: account.last_sync,
      ref: { type: "account", account },
    });
  }

  for (const email of awaitingMail(input.emails)) {
    if (!inFront(email.front_id)) continue;
    shownEmails.add(email.id);
    const urgent = level(email) === "acao";
    const analysis = email.analysis!;
    items.push({
      key: `email:${email.id}`,
      group: urgent ? "agora" : "novidades",
      front_id: email.front_id,
      channel: "e-mail",
      title: email.subject || "(sem assunto)",
      reason: analysis.acao_sugerida || analysis.motivo,
      since: email.date,
      ref: { type: "email", email, suggestion: suggestionOf.get(email.id) },
    });
  }
  for (const suggestion of input.suggestions) {
    if (shownEmails.has(suggestion.email_id) || !inFront(suggestion.front_id))
      continue;
    items.push({
      key: `suggestion:${suggestion.id}`,
      group: "novidades",
      front_id: suggestion.front_id,
      channel: "e-mail",
      title: suggestion.title,
      reason: suggestion.summary,
      since: null,
      ref: { type: "suggestion", suggestion },
    });
  }

  const dueIds = new Set<number>();
  for (const demand of input.demands) {
    if (closed(demand) || !inFront(demand.front_id)) continue;
    const date = [demand.due, demand.return_date]
      .filter((v): v is string => !!v)
      .sort()[0];
    if (!date || date > input.today) continue;
    dueIds.add(demand.id);
    items.push({
      key: `demand:${demand.id}`,
      group: "hoje",
      front_id: demand.front_id,
      channel: demand.channel,
      title: demand.title,
      reason: date < input.today ? "Em atraso." : "Vence hoje.",
      since: null,
      ref: { type: "demand", demand },
    });
  }
  for (const demand of input.demands) {
    if (
      closed(demand) ||
      dueIds.has(demand.id) ||
      !inFront(demand.front_id) ||
      !FOLLOW_UP_STAGES.includes(demand.stage)
    )
      continue;
    items.push({
      key: `demand:${demand.id}`,
      group: "aguardando",
      front_id: demand.front_id,
      channel: demand.channel,
      title: demand.title,
      reason:
        demand.stage === "acompanhar"
          ? "Em acompanhamento."
          : "Proposta enviada, sem retorno.",
      since: null,
      ref: { type: "demand", demand },
    });
  }

  // Orçamentos primeiro, depois quem espera há mais tempo.
  const budget = (i: PriorityItem) =>
    i.ref.type === "email" && i.ref.email.analysis?.categoria === "orcamento"
      ? 0
      : 1;
  return items.sort(
    (a, b) =>
      budget(a) - budget(b) || waitingMs(b, input.now) - waitingMs(a, input.now),
  );
}

export function waitingLabel(iso: string | null, now: number): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  if (minutes < 1) return "agora há pouco";
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  const days = Math.round(hours / 24);
  return `há ${days} ${days === 1 ? "dia" : "dias"}`;
}
