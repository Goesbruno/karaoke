import { FormEvent, useCallback, useEffect, useState } from "react";
import { loadYouTubeApi } from "./adapters/youtubeIframe";
import { Library } from "./features/Library";
import { LyricsPage } from "./features/LyricsPage";
import { LiveRoom } from "./features/LiveRoom";
import { NetworkPanel } from "./features/NetworkPanel";
import { Queue } from "./features/Queue";
import { Search } from "./features/Search";
import { useSession } from "./hooks/useSession";
import { usePolling } from "./hooks/usePolling";
import type { ApiPort } from "./ports/api";

type Tab = "buscar" | "fila" | "biblioteca" | "letras" | "cantar" | "rede";

export function App({ api }: { api: ApiPort }) {
  const { state, login } = useSession(api);
  const [tab, setTab] = useState<Tab>("buscar");
  const [manual, setManual] = useState("");
  const [lyricsSongId, setLyricsSongId] = useState<string | null>(null);
  const [singId, setSingId] = useState<string | null>(null);
  const songs = usePolling(useCallback(() => api.listSongs(), [api]), 5000);

  // Pré-carrega a API do YouTube para que a prévia comece logo após o clique.
  useEffect(() => { void loadYouTubeApi().catch(() => undefined); }, []);

  if (state.status === "loading") return <main><p>Conectando…</p></main>;
  if (state.status !== "ready") {
    const submit = (e: FormEvent) => { e.preventDefault(); void login(manual.trim()); };
    return (
      <main>
        <h1>Bruno o quê?</h1>
        {state.status === "denied" && <p role="alert" className="error">Token inválido ou expirado. Escaneie o QR code novamente.</p>}
        <p>Escaneie o QR code exibido pelo host ou informe o token de acesso. O token do host libera o envio de arquivos.</p>
        <form onSubmit={submit} className="row">
          <input aria-label="Token de acesso" type="password" value={manual} onChange={(e) => setManual(e.target.value)} />
          <button type="submit" disabled={!manual.trim()}>Entrar</button>
        </form>
      </main>
    );
  }
  const isHost = state.role === "host";
  // "letras" é aberta pelo card da biblioteca, não pela barra superior.
  const tabs: Tab[] = isHost ? ["buscar", "fila", "biblioteca", "cantar", "rede"] : ["buscar", "fila", "biblioteca", "cantar"];
  const list = songs.data ?? [];
  return (
    <main>
      <header className="row">
        <h1>Bruno o quê?</h1>
        <span className="badge">{isHost ? "Host" : "Convidado"}</span>
      </header>
      {songs.error && <p role="alert" className="error">{songs.error}</p>}
      <nav className="row" aria-label="Seções">
        {tabs.map((t) => <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>)}
      </nav>
      {tab === "buscar" && <Search api={api} isHost={isHost} onAdded={() => void songs.reload()} />}
      {tab === "fila" && <Queue api={api} songs={list} isHost={isHost} />}
      {tab === "biblioteca" && (
        <Library api={api} songs={list} isHost={isHost} reload={() => void songs.reload()}
                 onChooseLyrics={(s) => { setLyricsSongId(s.id); setTab("letras"); }}
                 onSing={(s) => { setSingId(s.id); setTab("cantar"); }} />
      )}
      {tab === "letras" && (
        <LyricsPage api={api} songs={list} isHost={isHost} refresh={() => void songs.reload()}
                    initialSongId={lyricsSongId ?? undefined} onBack={() => setTab("biblioteca")} />
      )}
      {tab === "cantar" && <LiveRoom api={api} songs={list} isHost={isHost} autoSelectId={singId} onAutoSelected={() => setSingId(null)} />}
      {tab === "rede" && isHost && <NetworkPanel api={api} />}
    </main>
  );
}
