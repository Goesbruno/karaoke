import { useEffect, useRef, useState } from "react";
import type { ApiPort } from "../ports/api";
import type { Song } from "../domain/types";

const CACHE_LIMIT = 3;
const cache = new Map<string, Promise<string>>();

/** Reutiliza o áudio já baixado para que repetir a prévia seja imediato. */
function blobFor(api: ApiPort, id: string): Promise<string> {
  const hit = cache.get(id);
  if (hit) return hit;
  const pending = api.audioBlobUrl(id, "instrumental");
  pending.catch(() => cache.delete(id));
  cache.set(id, pending);
  while (cache.size > CACHE_LIMIT) {
    const oldest = [...cache.keys()].find(k => k !== id);
    if (!oldest) break;
    const old = cache.get(oldest);
    cache.delete(oldest);
    void old?.then(u => URL.revokeObjectURL(u)).catch(() => undefined);
  }
  return pending;
}

/** Prévia local sem player visível: toca cerca de 5 s do meio do instrumental assim que o áudio estiver pronto. */
export function LocalPreview({ api, song, onClose }: { api: ApiPort; song: Song; onClose: () => void }) {
  const [message, setMessage] = useState("Preparando prévia…");
  const close = useRef(onClose);
  close.current = onClose;
  const stopNow = useRef<() => void>(() => undefined);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let closer: number | undefined;
    const audio = new Audio();
    audio.preload = "auto";
    stopNow.current = () => { audio.pause(); close.current(); };
    const finish = () => {
      if (!active) return;
      audio.pause();
      setMessage("Prévia encerrada.");
      closer = window.setTimeout(() => close.current(), 1200);
    };
    audio.addEventListener("playing", () => {
      if (!active) return;
      setMessage("Tocando prévia de 5 s…");
      window.clearTimeout(timer);
      timer = window.setTimeout(finish, 5000);
    }, { once: true });
    audio.addEventListener("error", () => { if (active) setMessage("Erro ao decodificar o áudio local."); });
    audio.addEventListener("loadedmetadata", () => {
      const d = audio.duration;
      audio.currentTime = Number.isFinite(d) && d > 0 ? Math.max(0, Math.min(d / 2, d - 5)) : 0;
      audio.play().catch(() => {
        if (active) setMessage("O navegador bloqueou a reprodução automática. Clique em Prévia local novamente.");
      });
    }, { once: true });

    blobFor(api, song.id).then(url => { if (active) audio.src = url; })
      .catch(e => { if (active) setMessage(e instanceof Error ? e.message : "Falha ao carregar a prévia."); });

    return () => {
      active = false;
      window.clearTimeout(timer);
      window.clearTimeout(closer);
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    };
  }, [api, song.id]);

  return (
    <div className="row local-preview" aria-label={`Prévia local de ${song.title}`}>
      <span role="status" className="hint">{message}</span>
      <button type="button" onClick={() => stopNow.current()}>Parar prévia</button>
    </div>
  );
}
