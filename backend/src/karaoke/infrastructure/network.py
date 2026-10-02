import ipaddress
from dataclasses import dataclass

VIRTUAL_HINTS = ("vethernet", "virtualbox", "vmware", "loopback", "docker", "wsl", "hyper-v", "vbox", "tailscale", "zerotier")

@dataclass(frozen=True)
class Iface:
    name: str
    ip: str
    private: bool
    virtual: bool

def discover_ipv4():
    import socket, psutil
    stats = psutil.net_if_stats()
    out = []
    for name, addrs in psutil.net_if_addrs().items():
        if name in stats and not stats[name].isup: continue
        for a in addrs:
            if a.family != socket.AF_INET: continue
            out.append((name, a.address))
    return classify(out)

def classify(pairs):
    res = []
    for name, ip in pairs:
        try: ad = ipaddress.ip_address(ip)
        except ValueError: continue
        if ad.is_loopback or ad.is_link_local or ad.is_unspecified or ad.is_multicast: continue
        res.append(Iface(name, ip, ad.is_private, any(h in name.lower() for h in VIRTUAL_HINTS)))
    return sorted(res, key=lambda i: (i.virtual, not i.private, i.name))

def choose(ifaces, preferred_ip=""):
    if preferred_ip:
        for i in ifaces:
            if i.ip == preferred_ip: return i
        raise ValueError(f"IP {preferred_ip} nao pertence a uma interface de rede ativa")
    return ifaces[0] if ifaces else None

def build_url(ip, port, token=None):
    ad = ipaddress.ip_address(ip)
    if ad.is_loopback or ad.is_unspecified:
        raise ValueError("URL de LAN nao pode usar localhost/0.0.0.0")
    base = f"http://{ip}:{port}/"
    return base + (f"#token={token}" if token else "")

def diagnose(ifaces, selected, port):
    msgs = []
    if not ifaces or selected is None:
        return ["Nenhuma interface IPv4 de rede local ativa. Conecte o servidor ao Wi-Fi ou cabo e reinicie."]
    if selected.virtual:
        msgs.append(f"A interface '{selected.name}' parece virtual (VM/VPN/WSL); celulares podem nao alcanca-la. Escolha outra.")
    if not selected.private:
        msgs.append(f"O IP {selected.ip} nao e de faixa privada; confirme que e o endereco da sua LAN.")
    msgs.append("Celulares e o servidor precisam estar na mesma rede (sem 'isolamento de clientes' no roteador).")
    msgs.append(f'Firewall (PowerShell como administrador): New-NetFirewallRule -DisplayName "Karaoke LAN" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow -Profile Private')
    msgs.append("Se o IP mudar (DHCP), reinicie o servidor para gerar novo QR code ou reserve o IP no roteador.")
    return msgs
