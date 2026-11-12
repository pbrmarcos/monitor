// Cores personalizáveis. As regras de contraste estão em docs/DESIGN.md.
export type Theme = { primary: string; accent: string };
export const defaultTheme: Theme = { primary: "#0D213A", accent: "#00D7EC" };
export const presets: (Theme & { name: string })[] = [
  { name: "Marinho", ...defaultTheme },
  { name: "Grafite", primary: "#1F2933", accent: "#F2B705" },
  { name: "Floresta", primary: "#14342B", accent: "#5FD38D" },
  { name: "Vinho", primary: "#3D1220", accent: "#FF8FA3" },
  { name: "Índigo", primary: "#241B4B", accent: "#A78BFA" },
  { name: "Petróleo", primary: "#0B3038", accent: "#FFB454" },
];
const CACHE = "monitor-theme";

const channels = (hex: string) =>
  [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
function luminance(hex: string) {
  const [r, g, b] = channels(hex).map((value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function contrast(first: string, second: string) {
  const [high, low] = [luminance(first), luminance(second)].sort(
    (a, b) => b - a,
  );
  return (high + 0.05) / (low + 0.05);
}
const mix = (hex: string, other: string, amount: number) =>
  "#" +
  channels(hex)
    .map((value, i) =>
      Math.round(value + (channels(other)[i] - value) * amount)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("");
export const valid = (hex: string) => /^#[0-9a-fA-F]{6}$/.test(hex);
/** A cor principal também é a cor do texto: precisa de contraste 7:1 com o branco. */
export const primaryOk = (hex: string) =>
  valid(hex) && contrast(hex, "#FFFFFF") >= 7;

export function applyTheme(theme: Theme, remember = true) {
  if (!primaryOk(theme.primary) || !valid(theme.accent)) return;
  const style = document.documentElement.style;
  style.setProperty("--navy", theme.primary);
  style.setProperty("--navy-2", mix(theme.primary, "#FFFFFF", 0.14));
  style.setProperty("--sidebar-line", mix(theme.primary, "#FFFFFF", 0.35));
  style.setProperty("--cyan", theme.accent);
  // Texto sobre a cor de destaque: o que tiver mais contraste.
  style.setProperty(
    "--on-cyan",
    contrast(theme.accent, theme.primary) >= contrast(theme.accent, "#FFFFFF")
      ? theme.primary
      : "#FFFFFF",
  );
  if (!remember) return;
  try {
    localStorage.setItem(CACHE, JSON.stringify(theme));
  } catch {
    // sem armazenamento local: as cores vêm do backend ao conectar
  }
}
/** Aplica as últimas cores usadas antes de o backend responder. */
export function applyCachedTheme() {
  try {
    const saved = JSON.parse(localStorage.getItem(CACHE) || "null");
    if (saved) applyTheme(saved, false);
  } catch {
    // ignora cache inválido
  }
}
