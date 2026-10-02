import re
from urllib.parse import parse_qs, urlsplit
from .errors import InvalidUrl

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}

def looks_like_url(q: str) -> bool:
    q = q.strip().lower()
    return q.startswith(("http://", "https://", "www.")) or "youtube.com/" in q or "youtu.be/" in q

def parse_youtube_url(raw: str) -> str:
    """Extrai o ID do video. Nunca faz requisicao de rede (sem risco de SSRF)."""
    raw = raw.strip()
    if raw.lower().startswith("www."): raw = "https://" + raw
    try:
        u = urlsplit(raw); port = u.port
    except ValueError:
        raise InvalidUrl("URL invalida")
    if u.scheme not in ("http", "https") or u.username or u.password or port not in (None, 80, 443):
        raise InvalidUrl("URL do YouTube invalida")
    host = (u.hostname or "").lower()
    if host in YT_HOSTS:
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [""])[0]
        else:
            m = re.fullmatch(r"/(?:shorts|embed|live)/([^/]+)", u.path)
            vid = m.group(1) if m else ""
    elif host in SHORT_HOSTS:
        vid = u.path.lstrip("/")
    else:
        raise InvalidUrl("dominio nao permitido; use youtube.com ou youtu.be")
    if not ID_RE.match(vid):
        raise InvalidUrl("ID de video invalido")
    return vid

def parse_iso_duration(s):
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s or "")
    if not m: return None
    d, h, mi, sec = (int(x or 0) for x in m.groups())
    return (d * 86400 + h * 3600 + mi * 60 + sec) or None
