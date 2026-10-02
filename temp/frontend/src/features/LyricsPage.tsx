import { useEffect, useState } from "react";
import type { ApiPort, LyricsRecord, LyricsSuggestion } from "../ports/api";
import type { Song } from "../domain/types";
import { LocalPreview } from "./LocalPreview";

export function LyricsPage({ api, songs, isHost, refresh }: {
  api: ApiPort; songs: Song[]; isHost: boolean; refresh: () => void;
}) {
  const [songId, setSongId] = useState("");
  const [selected, setSelected] = useState<LyricsRecord | null>(null);
  const [items, setItems] = useState<LyricsSuggestion[] | null>(null);
  const [excerpt, setExcerpt] = useState<number | null>(null);
  const [audio, setAudio] = useState<Song | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const current = songs.find(s => s.id === songId);

  useEffect(() => {
    let live = true;
    setSelected(null); setItems(null); setExcerpt(null); setAudio(null); setMessage("");
    if (songId) api.selectedLyrics(songId).then(r => { if (live) setSelected(r); })
      .catch(e => { if (live) setMessage(e instanceof Error ? e.message : "Erro de leitura."); });
    return () => { live = false; };
  }, [api, songId]);

  async function search() {
    if (!songId) return;
    setBusy(true); setMessage(""); setExcerpt(null);
    try {
      const result = await api.lyricsSuggestions(songId);
      setItems(result);
      if (!result.length) setMessage("Nenhuma sugestão. O host pode importar um .lrc autorizado.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "LRCLIB indisponível. A busca requer internet."); }
    finally { setBusy(false); }
  }
  async function choose(id: number) {
    setBusy(true);setMessage("");
    try {
      const record = await api.chooseLyrics(songId,id);
      setSelected(record);refresh();
      setMessage(record.status === "LETRA_SINCRONIZADA" ? "Letra sincronizada salva." :
        "Letra simples salva, sem timestamps. Importe um .lrc autorizado para sincronizar.");
    } catch(e) { setMessage(e instanceof Error ? e.message : "Erro ao escolher letra."); }
    finally { setBusy(false); }
  }
  async function upload(file?: File) {
    if (!file || !songId) return;
    setBusy(true);setMessage("");
    try { const r=await api.importLrc(songId,file);setSelected(r);refresh();setMessage("LRC sincronizado salvo."); }
    catch(e) { setMessage(e instanceof Error ? e.message : "Arquivo .lrc inválido."); }
    finally { setBusy(false); }
  }
  function format(n: number | null) {
    return n == null ? "—" : `${Math.floor(n/60)}:${String(Math.floor(n%60)).padStart(2,"0")}`;
  }

  return <section>
    <h2>Escolher letra</h2>
    <label>Música <select aria-label="Música para a letra" value={songId} onChange={e => setSongId(e.target.value)}>
      <option value="">Selecione uma música</option>
      {songs.filter(s=>s.status==="CONCLUIDA").map(s=><option key={s.id} value={s.id}>{s.title} — {s.artist}</option>)}
    </select></label>
    {current && <>
      <p>Status: {selected?.status ?? "SEM_LETRA"} · Origem: {selected?.source ?? "—"}</p>
      {selected?.content && <details><summary>Visualizar letra selecionada</summary><pre style={{whiteSpace:"pre-wrap"}}>{selected.content}</pre></details>}
      <p className="hint">LRCLIB requer internet. A letra escolhida fica salva localmente.</p>
      <div className="row">
        <button disabled={busy} onClick={() => void search()}>Buscar na LRCLIB</button>
        {current.library?.ready && <button onClick={() => setAudio(audio?.id===current.id?null:current)}>Ouvir instrumental local</button>}
      </div>
      {audio && <LocalPreview api={api} song={audio} onClose={() => setAudio(null)} />}
      {message && <p role="status">{message}</p>}
      {items && <ul className="cards">{items.map(item=><li className="card col" key={item.id}>
        <strong>{item.track_name || "Sem título"} — {item.artist_name || "Artista desconhecido"}</strong>
        <span>Duração: {format(item.duration)} · {item.synced ? "Sincronizada" : "Sem timestamps"}</span>
        <button onClick={() => setExcerpt(excerpt===item.id?null:item.id)}>Visualizar trecho</button>
        {excerpt===item.id && <pre style={{whiteSpace:"pre-wrap"}}>{item.preview}</pre>}
        {isHost && <button disabled={busy} onClick={() => void choose(item.id)}>Selecionar letra</button>}
      </li>)}</ul>}
      {isHost && <label>Importar .lrc autorizado <input type="file" accept=".lrc,text/plain"
        onChange={e=>{void upload(e.target.files?.[0]);e.target.value="";}} /></label>}
    </>}
    <p className="hint">Letra simples não sincroniza. A tela de canto ainda não foi implementada.</p>
  </section>;
}
