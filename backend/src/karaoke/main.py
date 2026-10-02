import uvicorn
from .config import Settings
from .infrastructure import network as net
from .infrastructure.sqlite_store import SqliteStore
from .interfaces.api import create_app

def main():
    s = Settings.from_env()
    ifs = net.discover_ipv4()
    sel = net.choose(ifs, s.advertise_ip)
    if sel:
        from .infrastructure.qr import qr_ascii
        url = net.build_url(sel.ip, s.port, s.guest_token)
        print(f"Interface: {sel.name} ({sel.ip})  Porta: {s.port}")
        print(f"URL de convidado: {url}\n{qr_ascii(url)}")
        if len(ifs) > 1:
            print("Outras interfaces:", ", ".join(f"{i.name}={i.ip}" for i in ifs if i != sel),
                  "| use KARAOKE_ADVERTISE_IP para escolher")
    for m in net.diagnose(ifs, sel, s.port): print(" -", m)
    print(f"Token do host: {s.host_token}")
    print("Dependem de internet: YouTube, LRCLIB e iTunes (se habilitado). A LAN funciona sem internet.")
    uvicorn.run(create_app(s, SqliteStore(s.db_path)), host=s.host, port=s.port)

if __name__ == "__main__":
    main()
