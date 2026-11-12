import type {
  Analysis,
  Demand,
  Email,
  SocialProfile,
  Suggestion,
} from "./api";

export const today = () => new Date().toLocaleDateString("en-CA");
const hoursAgo = (hours: number) =>
  new Date(Date.now() - hours * 3600000).toISOString();

const profile = (
  id: number,
  username: string,
  name: string,
  followers: number,
  posts: number,
  week: [number, number, number, number, number],
): SocialProfile => ({
  id,
  front_id: id,
  network: "instagram",
  username,
  name,
  avatar: "",
  status: "ok",
  status_detail: "",
  last_sync: hoursAgo(1),
  followers,
  posts,
  followers_change: week[0],
  change_days: 7,
  posts_week: week[1],
  stories_week: week[2],
  likes_week: week[3],
  comments_week: week[4],
});
export const demoSocial: SocialProfile[] = [
  profile(1, "rocha.exemplo", "Rocha Comercial", 2480, 214, [124, 3, 9, 412, 37]),
  profile(2, "nextlink.exemplo", "Nextlink", 1820, 156, [68, 2, 5, 268, 19]),
  profile(3, "carteira.exemplo", "Carteira Pronta", 965, 88, [-4, 1, 0, 97, 6]),
  profile(4, "webq.exemplo", "WebQ", 3210, 302, [146, 4, 12, 655, 48]),
];

export const demoDemands: Demand[] = [
  {
    id: 1,
    title: "Preparar proposta para Ana",
    front_id: 1,
    contact: "Ana · exemplo",
    channel: "email",
    stage: "preparar_proposta",
    priority: "alta",
    due: today(),
    next_action: "Revisar escopo e enviar pelo canal original",
    return_date: null,
    summary: "Pedido de orçamento fictício para explorar o painel.",
  },
  {
    id: 2,
    title: "Revisar briefing do projeto",
    front_id: 2,
    contact: "Pedro · exemplo",
    channel: "email",
    stage: "qualificacao",
    priority: "normal",
    due: today(),
    next_action: "Conferir os materiais recebidos",
    return_date: null,
    summary: "Briefing ilustrativo.",
  },
  {
    id: 3,
    title: "Atualizar apresentação comercial",
    front_id: 3,
    contact: "",
    channel: "manual",
    stage: "novo",
    priority: "normal",
    due: null,
    next_action: "Selecionar os projetos recentes",
    return_date: null,
    summary: "",
  },
  {
    id: 4,
    title: "Retornar sobre proposta enviada",
    front_id: 4,
    contact: "Clara · exemplo",
    channel: "manual",
    stage: "acompanhar",
    priority: "normal",
    due: null,
    next_action: "Consultar o retorno do cliente",
    return_date: today(),
    summary: "Acompanhamento de demonstração.",
  },
];

const analysis = (values: Partial<Analysis>): Analysis => ({
  categoria: "outro",
  importancia: "revisar",
  motivo: "",
  resumo: "",
  acao_sugerida: null,
  prazo_texto: null,
  prazo_iso: null,
  trecho_prazo: null,
  confianca: 0.9,
  modelo: "demonstração",
  correcao: null,
  provisional: false,
  ...values,
});
const email = (
  id: number,
  front: number,
  sender: string,
  subject: string,
  body: string,
  result: Partial<Analysis>,
): Email => ({
  id,
  account_id: front,
  account: `contato@${["rochacomercial", "nextlink", "carteirapronta", "webq"][front - 1]}.example`,
  front_id: front,
  sender,
  subject,
  date: hoursAgo(id * 3),
  body,
  has_attachments: false,
  analysis_status: "analisado",
  analysis: analysis({ resumo: body, ...result }),
  demand_id: null,
  suggestion_id: id === 1 ? 1 : null,
});

export const demoEmails: Email[] = [
  email(
    1,
    1,
    "Ana Souza <ana@cliente.example>",
    "Orçamento para novo projeto",
    "Olá, Marcos! Gostaria de receber um orçamento para nosso novo projeto. Preciso da proposta até sexta.",
    {
      categoria: "orcamento",
      importancia: "acao",
      motivo: "Pedido de orçamento com prazo.",
      acao_sugerida: "Enviar proposta para Ana",
      prazo_texto: "sexta",
      trecho_prazo: "Preciso da proposta até sexta.",
    },
  ),
  email(
    2,
    2,
    "Pedro Lima <pedro@cliente.example>",
    "Briefing e referências",
    "Segue o briefing para revisão. Podemos alinhar os detalhes na próxima conversa?",
    {
      categoria: "cliente",
      importancia: "importante",
      motivo: "Cliente enviou material para revisão.",
      acao_sugerida: "Revisar o briefing",
    },
  ),
  email(
    3,
    3,
    "Boletim de design <newsletter@boletim.example>",
    "Referências da semana",
    "Uma seleção de novidades e referências para sua leitura.",
    {
      categoria: "publicidade",
      importancia: "info",
      motivo: "Boletim informativo.",
    },
  ),
  email(
    4,
    4,
    "Carla Dias <carla@fornecedor.example>",
    "Sobre a entrega do material",
    "Oi! Acho que conseguimos entregar na semana que vem, mas ainda preciso confirmar.",
    {
      categoria: "fornecedor",
      importancia: "revisar",
      motivo: "Data ambígua, confira o prazo.",
      prazo_texto: "semana que vem",
    },
  ),
];
export const demoSuggestions: Suggestion[] = [
  {
    id: 1,
    email_id: 1,
    front_id: 1,
    title: "Enviar proposta para Ana",
    contact: "Ana Souza <ana@cliente.example>",
    summary: "Pedido de orçamento para um novo projeto, com prazo até sexta.",
    due: null,
  },
];
export const files = [
  { name: "Proposta_Ana.pdf", front: 1, category: "Proposta", size: "248 KB" },
  {
    name: "Briefing_projeto.docx",
    front: 2,
    category: "Briefing",
    size: "1,2 MB",
  },
  {
    name: "Apresentação_comercial.pdf",
    front: 3,
    category: "Material",
    size: "4,8 MB",
  },
];
