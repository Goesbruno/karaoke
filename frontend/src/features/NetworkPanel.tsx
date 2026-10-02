import { useEffect, useState } from "react";
import type { NetworkInfo } from "../domain/types";
import type { ApiPort } from "../ports/api";

const QR_WHITE_KEY = "karaoke.qrWhite";

export function NetworkPanel({ api }: { api: ApiPort }) {
  const [info, setInfo] = useState<NetworkInfo | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [white, setWhite] = useState(() => {
    try { return localStorage.getItem(QR_WHITE_KEY) === "1"; } catch { return false; }
  });

  useEffect(() => {
    let url: string | null = null;
    api.network().then(setInfo).catch((e) => setErr(e.message));
    api.qrObjectUrl().then((u) => { url = u; setQr(u); }).catch(() => undefined);
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [api]);

  function toggle() {
    setWhite((v) => {
      const next = !v;
      try { localStorage.setItem(QR_WHITE_KEY, next ? "1" : "0"); } catch { /* armazenamento indisponível */ }
      return next;
    });
  }

  if (err) return <p role="alert" className="error">{err}</p>;
  if (!info) return <p>Carregando…</p>;
  return (
    <div>
      {qr ? (
        <div className="col qr-box">
          <div className="qr-tile" style={{ background: white ? "#000" : "#fff" }}>
            <img src={qr} alt="QR code de acesso para convidados" width={240} height={240}
                 style={{ filter: white ? "invert(1)" : "none" }} />
          </div>
          <button type="button" aria-pressed={white} onClick={toggle}>
            {white ? "Usar QR code preto" : "Usar QR code branco"}
          </button>
        </div>
      ) : <p>QR code indisponível (sem interface de LAN).</p>}
      <p>Endereço: <code>{info.url ?? "indisponível"}</code></p>
      <h3>Interfaces</h3>
      <ul>{info.interfaces.map((i) => <li key={i.ip}>{i.name} — {i.ip}{i.virtual ? " (virtual)" : ""}{info.selected?.ip === i.ip ? " ← anunciada" : ""}</li>)}</ul>
      <p className="hint">Para anunciar outra interface, defina KARAOKE_ADVERTISE_IP e reinicie o servidor.</p>
      <h3>Diagnóstico</h3>
      <ul>{info.diagnostics.map((d) => <li key={d}>{d}</li>)}</ul>
      <h3>Dependem de internet</h3>
      <ul>{info.internet_dependencies.map((d) => <li key={d}><span className="badge">Requer internet</span> {d}</li>)}</ul>
    </div>
  );
}
