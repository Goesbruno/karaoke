export function formatDuration(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s) || s < 0) return "—";
  const t = Math.round(s);
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${p(m)}:${p(sec)}` : `${m}:${p(sec)}`;
}

export const PREVIEW_SECONDS = 5;

export type PreviewPlan = { ok: true; start: number; length: number } | { ok: false; reason: string };

/** Começa na metade da duração, garantindo que os 5 s caibam no vídeo. */
export function previewPlan(duration: number | null | undefined): PreviewPlan {
  if (duration == null || !Number.isFinite(duration) || duration <= 0) {
    return { ok: false, reason: "Duração indisponível: não é possível calcular o meio do vídeo." };
  }
  if (duration <= PREVIEW_SECONDS) return { ok: true, start: 0, length: duration };
  const start = Math.max(0, Math.min(Math.floor(duration / 2), Math.floor(duration - PREVIEW_SECONDS)));
  return { ok: true, start, length: PREVIEW_SECONDS };
}

export const STATE_LABEL: Record<string, string> = {
  AGUARDANDO_UPLOAD: "Aguardando upload",
  NA_FILA: "Na fila",
  PREPARANDO: "Preparando",
  SEPARANDO_INSTRUMENTAL_VOCAIS: "Separando instrumental e vocais",
  SEPARANDO_LEAD_BACKING: "Separando vocal principal e backing",
  ANALISANDO: "Analisando",
  CONCLUIDA: "Concluída",
  FALHA: "Falha",
  CANCELADA: "Cancelada",
};
export const ACTIVE_STATES = ["PREPARANDO", "SEPARANDO_INSTRUMENTAL_VOCAIS", "SEPARANDO_LEAD_BACKING", "ANALISANDO"];
