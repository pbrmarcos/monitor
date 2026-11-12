import type { LucideIcon } from "lucide-react";
import { Inbox, Info } from "lucide-react";
import type { ReactNode } from "react";

// Nomes padrão das frentes (FRONTS em app/backend/monitor/models.py). O usuário
// pode trocá-los em Configurações; a store chama setFrontNames ao carregar.
export const defaultFronts = [
  "Rocha Comercial",
  "Nextlink",
  "Carteira Pronta",
  "WebQ",
];
let fronts = defaultFronts;
export const setFrontNames = (names: string[]) => {
  fronts = names.length === 4 ? names : defaultFronts;
};
export const frontLabel = (front: number) =>
  fronts[front - 1] ?? `Frente ${front}`;

const initials = (name: string) =>
  name
    .replace(/^@/, "")
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "?";
export function FrontIcon({
  src,
  name,
  large = false,
}: {
  src?: string;
  name: string;
  large?: boolean;
}) {
  return (
    <span className={`front-icon${large ? " lg" : ""}`} aria-hidden>
      {src ? <img src={src} alt="" /> : initials(name)}
    </span>
  );
}

export function Avatar({
  src,
  name,
  size = "",
}: {
  src?: string;
  name: string;
  size?: "" | "lg";
}) {
  return (
    <span className={`avatar ${size}`} aria-hidden>
      {src ? <img src={src} alt="" /> : initials(name)}
    </span>
  );
}

export const dateLabel = (date: string | null) =>
  date
    ? new Date(date + "T12:00:00").toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "short",
      })
    : "Sem prazo";

export const timeLabel = (iso: string | null) => {
  if (!iso) return "";
  const date = new Date(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
};

export const senderName = (sender: string) =>
  sender.replace(/\s*<[^>]*>\s*$/, "").replace(/^"|"$/g, "") || sender;

export function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({
  icon: Icon = Inbox,
  text,
  children,
}: {
  icon?: LucideIcon;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Icon size={24} aria-hidden />
      <p>{text}</p>
      {children}
    </div>
  );
}

export function Callout({
  icon: Icon = Info,
  tone = "",
  role,
  children,
  action,
}: {
  icon?: LucideIcon;
  tone?: "" | "error";
  role?: "alert" | "status";
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={`callout ${tone}`} role={role}>
      <Icon size={18} aria-hidden />
      <p>{children}</p>
      {action}
    </div>
  );
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
}: {
  items: { id: T; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          role="tab"
          aria-selected={value === item.id}
          onClick={() => onChange(item.id)}
        >
          {item.id}
          {item.count !== undefined && (
            <span className="count">{item.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

export const soon = <span className="badge">Em breve</span>;
export const sample = <span className="badge">Demonstração</span>;
