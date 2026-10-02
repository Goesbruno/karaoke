import { FormEvent, useState } from "react";
import { formatDuration } from "../domain/format";
import type { SearchItem, SearchResponse, Song } from "../domain/types";
import { ApiError, type ApiPort } from "../ports/api";
import { PreviewPlayer } from "./PreviewPlayer";
import { HOMONYM_QUESTION, uploadSong } from "./uploadFlow";

const ERR: Record<string, string> = {
  sem_internet: "Sem internet no servidor: a pesquisa no YouTube está indisponível.",
  youtube_cota: "A cota diária da YouTube Data API foi esgotada.",
  youtube_nao_configurado: "O host ainda não configurou a chave da YouTube Data API.",
  url_invalida: "URL inválida. Use um link de vídeo do youtube.com ou youtu.be.",
};

export function Search({ api, onAdded, isHost }: { api: ApiPort; onAdded: (s: Song) => void; isHost: boolean }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resp, setResp] = useState<SearchResponse | null>(null);
  const [preview, setPreview] = useState<SearchItem | null>(null);
  const [adding, setAdding] = useState<SearchItem | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<Song | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setNotice(""); setAdding(null);
    try { setResp(await api.search(q)); }
    catch (err) {
      setResp(null);
      setError(err instanceof ApiError ? (err.code && ERR[err.code]) || err.message : "Erro inesperado.");
    } finally { setBusy(false); }
  }

  async function confirmAdd(e: FormEvent) {
    e.preventDefault();
    if (!adding) return;
    try {
      const s = await api.createSong({ title, artist, source_video_id: adding.video_id });
      setNotice(`"${s.title}" foi adicionada e aguarda o arquivo de áudio autorizado.`);
      setPending(s); setUploadMsg(""); setAdding(null); onAdded(s);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Erro inesperado."); }
  }

  async function onFile(file: File | undefined) {
    if (!file || !pending) return;
    const r = await uploadSong(api, pending.id, file, () => window.confirm(HOMONYM_QUESTION));
    if (r.ok) { setNotice(r.message); setPending(null); setUploadMsg(""); onAdded(pending); }
    else setUploadMsg(r.message);
  }

  return (
    <div>
      <form onSubmit={submit} className="row" role="search">
        <input aria-label="Nome da música ou URL do YouTube" placeholder="Nome da música ou URL do vídeo do YouTube"
               value={q} onChange={(e) => setQ(e.target.value)} />
        <button type="submit" disabled={busy || !q.trim()}>Buscar</button>
      </form>
      <p className="hint"><span className="badge">Requer internet</span> Pesquisa e prévia usam o YouTube (API oficial e player oficial). O áudio da música vem de um arquivo que você envia.</p>
      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status" className="ok">{notice}</p>}
      {pending && (
        <section className="card col" aria-label="Enviar áudio">
          <strong>Passo 2: arquivo de áudio de "{pending.title}"</strong>
          {isHost ? (
            <>
              <p className="hint">Envie um arquivo que você tem autorização para usar (mp3, wav, flac, m4a ou ogg).</p>
              <label>Arquivo de áudio autorizado{" "}
                <input type="file" accept=".mp3,.wav,.flac,.m4a,.ogg,audio/*" onChange={(e) => void onFile(e.target.files?.[0])} />
              </label>
            </>
          ) : (
            <p>Aguardando o host enviar o arquivo de áudio desta música (aba Biblioteca do host).</p>
          )}
          {uploadMsg && <p role="alert" className="error">{uploadMsg}</p>}
        </section>
      )}
      {resp && (
        <p className="hint">
          {resp.mode === "url" ? "Vídeo correspondente à URL informada (sem pesquisa textual)." : "Até 5 resultados de pesquisa."}{" "}
          Fonte: {resp.attribution}.
        </p>
      )}
      <ul className="cards">
        {resp?.items.map((it) => (
          <li key={it.video_id} className="card">
            {it.thumbnail && <img src={it.thumbnail} alt="" width={160} height={90} />}
            <div>
              <strong>{it.title}</strong>
              <div>Canal: {it.channel}</div>
              <div>Duração: {formatDuration(it.duration_s)}</div>
              <div className="hint">Dados do vídeo no YouTube; o nome da música e o artista podem precisar de correção.</div>
              <div className="row">
                <button onClick={() => setPreview(it)}>Prévia</button>
                <button onClick={() => { setAdding(it); setTitle(it.title); setArtist(""); }}>Adicionar</button>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {resp && resp.items.length === 0 && <p>Nenhum vídeo encontrado.</p>}
      {preview && <PreviewPlayer item={preview} onClose={() => setPreview(null)} />}
      {adding && (
        <form onSubmit={confirmAdd} className="card col">
          <p className="hint">Título sugerido a partir do vídeo — corrija se necessário.</p>
          <label>Título da música <input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label>Artista <input value={artist} onChange={(e) => setArtist(e.target.value)} /></label>
          <div className="row">
            <button type="submit" disabled={!title.trim()}>Confirmar</button>
            <button type="button" onClick={() => setAdding(null)}>Cancelar</button>
          </div>
        </form>
      )}
    </div>
  );
}
