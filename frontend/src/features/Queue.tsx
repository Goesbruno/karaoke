import { ACTIVE_STATES, STATE_LABEL } from "../domain/format";
import type { Job, Song } from "../domain/types";
import type { ApiPort } from "../ports/api";
import { usePolling } from "../hooks/usePolling";

export function Queue({ api, songs, isHost }: { api: ApiPort; songs: Song[]; isHost: boolean }) {
  const { data, error, reload } = usePolling<Job[]>(() => api.listJobs(), 3000);
  const title = (id: string) => songs.find((s) => s.id === id)?.title ?? id.slice(0, 8);
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); } finally { void reload(); } };
  if (error) return <p role="alert" className="error">{error}</p>;
  if (!data) return <p>Carregando fila…</p>;
  if (!data.length) return <p>A fila está vazia.</p>;
  return (
    <table>
      <thead><tr><th>Música</th><th>Estado</th><th>Posição</th><th>Tentativas</th><th>Detalhes</th>{isHost && <th />}</tr></thead>
      <tbody>
        {data.map((j) => (
          <tr key={j.id}>
            <td>{title(j.song_id)}</td>
            <td>{STATE_LABEL[j.state] ?? j.state}</td>
            <td>{j.position ?? "—"}</td>
            <td>{j.attempts}/{j.max_attempts}</td>
            <td>{j.error || j.message || j.step || "—"}</td>
            {isHost && (
              <td>
                {j.state === "FALHA" && <button onClick={() => act(() => api.retryJob(j.id))}>Tentar novamente</button>}
                {(j.state === "NA_FILA" || ACTIVE_STATES.includes(j.state)) &&
                  <button onClick={() => act(() => api.cancelJob(j.id))}>Cancelar</button>}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
