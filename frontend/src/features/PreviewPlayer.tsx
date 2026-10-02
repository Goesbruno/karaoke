import { useEffect, useRef, useState } from "react";
import { loadYouTubeApi, type YTPlayer } from "../adapters/youtubeIframe";
import { previewPlan } from "../domain/format";
import { mapYtError } from "../domain/ytErrors";
import type { SearchItem } from "../domain/types";

type Status = "loading" | "buffering" | "playing" | "stopped" | "blocked" | "error";
const LABEL: Record<Status, string> = {
  loading: "Carregando o player do YouTube…",
  buffering: "Carregando o vídeo (buffering)…",
  playing: "Reproduzindo prévia de ~5 s",
  stopped: "Prévia encerrada (aproximadamente 5 s; sem precisão de amostra).",
  blocked: "",
  error: "",
};

/**
 * Player oficial do YouTube fixo no canto da tela: a listagem continua visível e rolável.
 * Ele permanece visível (mínimo 200x200) porque as políticas da API não permitem
 * reprodução com o player oculto.
 */
export function PreviewPlayer({ item, onClose }: { item: SearchItem; onClose: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    let cancelled = false;
    let player: YTPlayer | null = null;
    let stopTimer: number | undefined;
    let watch: number | undefined;
    const plan = previewPlan(item.duration_s);
    setStatus("loading"); setMsg("");
    if (item.embeddable === false) {
      setStatus("error"); setMsg("Este vídeo não permite reprodução incorporada."); return;
    }
    if (!plan.ok) { setStatus("error"); setMsg(plan.reason); return; }

    const blocked = (text: string) => {
      window.clearTimeout(watch);
      setStatus("blocked"); setMsg(text);
    };

    loadYouTubeApi().then((YT) => {
      if (cancelled || !host.current) return;
      // iframe criado por nós, com permissão de autoplay delegada e política de referrer explícita
      const iframe = document.createElement("iframe");
      const params = new URLSearchParams({
        enablejsapi: "1", autoplay: "1", start: String(plan.start),
        playsinline: "1", rel: "0", origin: window.location.origin,
      });
      iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(item.video_id)}?${params.toString()}`;
      iframe.width = "320"; iframe.height = "200";
      iframe.title = "Player oficial do YouTube";
      iframe.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      host.current.replaceChildren(iframe);
      watch = window.setTimeout(
        () => blocked("A prévia não iniciou. Se o navegador bloqueou a reprodução automática, toque em ▶ no player."),
        10000,
      );
      player = new YT.Player(iframe, {
        events: {
          onAutoplayBlocked: () => blocked("O navegador bloqueou a reprodução automática. Toque em ▶ no player para ouvir a prévia."),
          onStateChange: (e) => {
            if (e.data === YT.PlayerState.BUFFERING) setStatus("buffering");
            if (e.data === YT.PlayerState.PLAYING) {
              window.clearTimeout(watch); setStatus("playing"); setMsg("");
              if (stopTimer === undefined) {
                stopTimer = window.setTimeout(() => { player?.pauseVideo(); setStatus("stopped"); }, plan.length * 1000);
              }
            }
          },
          onError: (e) => { window.clearTimeout(watch); setStatus("error"); setMsg(mapYtError(e.data)); },
        },
      });
    }).catch(() => {
      if (!cancelled) { setStatus("error"); setMsg("Não foi possível carregar o player do YouTube. Verifique a internet."); }
    });

    return () => {
      cancelled = true;
      window.clearTimeout(stopTimer); window.clearTimeout(watch);
      try { player?.destroy(); } catch { /* já destruído */ }
    };
  }, [item.video_id, item.duration_s, item.embeddable]);

  return (
    <section className="preview preview-dock" aria-label="Prévia do YouTube">
      <div className="row">
        <strong className="preview-title">Prévia: {item.title}</strong>
        <button type="button" onClick={onClose}>Fechar</button>
      </div>
      <div ref={host} className="player-box" />
      <p role="status">{msg || LABEL[status]}</p>
      <a href={`https://www.youtube.com/watch?v=${item.video_id}`} target="_blank" rel="noreferrer noopener">
        Abrir no YouTube
      </a>
    </section>
  );
}
