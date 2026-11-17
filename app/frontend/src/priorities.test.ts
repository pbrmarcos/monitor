import { describe, expect, it } from "vitest";
import type { Demand, Email, Suggestion } from "./api";
import {
  awaitingMail,
  buildPriorities,
  mailCounts,
  waitingLabel,
} from "./priorities";

const NOW = Date.parse("2026-11-17T15:00:00Z");
const TODAY = "2026-11-17";

const email = (id: number, level: string, extra: Partial<Email> = {}) =>
  ({
    id,
    account_id: 1,
    account: "a@b.com",
    front_id: 1,
    sender: "Cliente <c@x.com>",
    subject: `Assunto ${id}`,
    date: "2026-11-17T13:00:00Z",
    body: "",
    has_attachments: false,
    analysis_status: "ok",
    demand_id: null,
    suggestion_id: null,
    analysis: {
      categoria: "outro",
      importancia: level,
      motivo: "motivo",
      acao_sugerida: null,
    },
    ...extra,
  }) as unknown as Email;

const demand = (id: number, extra: Partial<Demand> = {}): Demand => ({
  id,
  title: `Demanda ${id}`,
  front_id: 1,
  contact: "",
  channel: "manual",
  stage: "novo",
  priority: "normal",
  due: null,
  next_action: "",
  return_date: null,
  summary: "",
  ...extra,
});

const base = {
  demands: [] as Demand[],
  emails: [] as Email[],
  suggestions: [] as Suggestion[],
  accounts: [],
  sites: [],
  front: 0,
  today: TODAY,
  now: NOW,
};

describe("contagem de e-mails", () => {
  it("separa o que espera decisão do que já virou demanda", () => {
    const emails = [
      email(1, "acao"),
      email(2, "acao", { demand_id: 9 }),
      email(3, "importante"),
      email(4, "info"),
    ];
    expect(awaitingMail(emails).map((e) => e.id)).toEqual([1, 3]);
    expect(mailCounts(emails)).toMatchObject({
      acao: 2,
      importante: 1,
      acaoSemDemanda: 1,
      comDemanda: 1,
    });
  });
});

describe("buildPriorities", () => {
  it("agrupa e-mail de ação em 'agora' e importante em 'novidades'", () => {
    const items = buildPriorities({
      ...base,
      emails: [email(1, "acao"), email(2, "importante")],
    });
    expect(items.find((i) => i.key === "email:1")?.group).toBe("agora");
    expect(items.find((i) => i.key === "email:2")?.group).toBe("novidades");
  });

  it("coloca orçamento antes e depois quem espera há mais tempo", () => {
    const orcamento = email(3, "acao", { date: "2026-11-17T14:30:00Z" });
    orcamento.analysis!.categoria = "orcamento";
    const items = buildPriorities({
      ...base,
      emails: [
        email(1, "acao", { date: "2026-11-17T14:00:00Z" }),
        email(2, "acao", { date: "2026-11-16T10:00:00Z" }),
        orcamento,
      ],
    });
    expect(items.map((i) => i.key)).toEqual(["email:3", "email:2", "email:1"]);
  });

  it("não duplica sugestão cujo e-mail já está na fila", () => {
    const suggestion = { id: 7, email_id: 1, front_id: 1 } as Suggestion;
    const items = buildPriorities({
      ...base,
      emails: [email(1, "acao", { suggestion_id: 7 })],
      suggestions: [suggestion],
    });
    expect(items).toHaveLength(1);
    expect(items[0].ref).toMatchObject({ type: "email", suggestion });
  });

  it("separa demandas de hoje das que aguardam terceiros", () => {
    const items = buildPriorities({
      ...base,
      demands: [
        demand(1, { due: TODAY }),
        demand(2, { due: "2026-11-10" }),
        demand(3, { stage: "proposta_enviada" }),
        demand(4, { stage: "proposta_enviada", due: TODAY }),
        demand(5, { stage: "ganho", due: TODAY }),
        demand(6, { due: "2026-12-01" }),
      ],
    });
    const group = (g: string) =>
      items.filter((i) => i.group === g).map((i) => i.key).sort();
    expect(group("hoje")).toEqual(["demand:1", "demand:2", "demand:4"]);
    expect(group("aguardando")).toEqual(["demand:3"]);
    expect(items.some((i) => i.key === "demand:5")).toBe(false);
  });

  it("sobe site fora do ar e conta com erro para 'agora'", () => {
    const items = buildPriorities({
      ...base,
      sites: [
        {
          id: 1,
          name: "Loja",
          front_id: 2,
          enabled: true,
          latest: { ok: false, checked_at: "2026-11-17T14:55:00Z" },
        },
        {
          id: 2,
          name: "Blog",
          front_id: 2,
          enabled: true,
          latest: { ok: true, checked_at: "2026-11-17T14:55:00Z" },
        },
      ] as never,
      accounts: [
        { id: 4, front_id: 3, address: "x@y.com", status: "erro" },
      ] as never,
    });
    expect(items.map((i) => [i.key, i.group])).toEqual(
      expect.arrayContaining([
        ["site:1", "agora"],
        ["account:4", "agora"],
      ]),
    );
    expect(items.some((i) => i.key === "site:2")).toBe(false);
  });

  it("respeita o filtro de frente", () => {
    const items = buildPriorities({
      ...base,
      front: 2,
      emails: [email(1, "acao", { front_id: 1 }), email(2, "acao", { front_id: 2 })],
    });
    expect(items.map((i) => i.key)).toEqual(["email:2"]);
  });
});

describe("waitingLabel", () => {
  it("descreve o tempo de espera", () => {
    expect(waitingLabel(null, NOW)).toBe("");
    expect(waitingLabel("2026-11-17T14:40:00Z", NOW)).toBe("há 20 min");
    expect(waitingLabel("2026-11-17T13:00:00Z", NOW)).toBe("há 2 h");
    expect(waitingLabel("2026-11-15T15:00:00Z", NOW)).toBe("há 2 dias");
  });
});
