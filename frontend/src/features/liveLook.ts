export const MAX_BLUR = 30;

export function clampBlur(v: number): number {
  return Number.isFinite(v) ? Math.min(MAX_BLUR, Math.max(0, Math.round(v))) : 0;
}
export function clampOpacity(v: number): number {
  return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 1;
}
export function clampContrast(v: number): number {
  return Number.isFinite(v) ? Math.min(100, Math.max(0, Math.round(v))) : 50;
}

/** Variáveis CSS da letra: mais contraste = fundo escuro atrás da linha e sombra mais forte. */
export function lyricStyle(level: number): Record<string, string> {
  const c = clampContrast(level) / 100;
  return {
    "--lyric-scrim": (c * 0.7).toFixed(2),
    "--lyric-shadow": (0.4 + c * 0.6).toFixed(2),
    "--lyric-dim": (0.35 + c * 0.35).toFixed(2),
  };
}

export function formatClock(ms: number): string {
  const s = Math.max(0, Math.floor((Number.isFinite(ms) ? ms : 0) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Campos em que a barra de espaço deve digitar/ativar o próprio controle, não tocar a música. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag === "INPUT") {
    const type = (target as HTMLInputElement).type;
    return !["range", "button", "checkbox", "radio", "submit"].includes(type);
  }
  return false;
}

const CONTRAST_KEY = "karaoke.lyricContrast";
export function loadContrast(): number {
  try {
    const raw = localStorage.getItem(CONTRAST_KEY);
    return raw === null ? 50 : clampContrast(Number(raw));
  } catch { return 50; }
}
export function saveContrast(v: number): void {
  try { localStorage.setItem(CONTRAST_KEY, String(clampContrast(v))); } catch { /* armazenamento indisponível */ }
}
