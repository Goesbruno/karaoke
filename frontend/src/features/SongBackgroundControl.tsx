import { useEffect, useState } from "react";
import type { ApiPort } from "../ports/api";

const TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_BYTES = 256000;

/** Imagem de fundo própria da música (somente o host a vê/usa). */
export function SongBackgroundControl({ api, songId, onChanged, label = "Imagem de fundo desta música (PNG, JPEG ou WebP até 256 KB)" }: {
  api: ApiPort; songId: string; onChanged?: () => void; label?: string;
}) {
  const [has, setHas] = useState<boolean | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    setHas(null); setMsg("");
    Promise.resolve().then(() => api.listBackgrounds())
      .then(r => { if (live) setHas(r.song_ids.includes(songId)); })
      .catch(() => { if (live) setHas(null); });
    return () => { live = false; };
  }, [api, songId]);

  async function choose(file?: File) {
    if (!file) return;
    if (!TYPES.includes(file.type) || file.size > MAX_BYTES) { setMsg("Use PNG, JPEG ou WebP de até 256 KB."); return; }
    setBusy(true); setMsg("");
    try {
      await api.setSongBackground(songId, file);
      setHas(true); setMsg("Imagem salva para esta música."); onChanged?.();
    } catch (e) { setMsg(e instanceof Error ? e.message : "Falha ao salvar a imagem."); }
    finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true); setMsg("");
    try {
      await api.clearSongBackground(songId);
      setHas(false); setMsg("Imagem removida."); onChanged?.();
    } catch (e) { setMsg(e instanceof Error ? e.message : "Falha ao remover a imagem."); }
    finally { setBusy(false); }
  }

  return (
    <div className="col bg-control">
      <label>{label}{" "}
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
               onChange={e => { void choose(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      <div className="row">
        <span className="hint">
          {has === null ? "Verificando imagem de fundo…" : has ? "Esta música tem imagem própria." : "Sem imagem própria: será usado o fundo padrão."}
        </span>
        {has && <button type="button" disabled={busy} onClick={() => void remove()}>Remover imagem</button>}
      </div>
      {msg && <p role="status" className="hint">{msg}</p>}
    </div>
  );
}
