import json, urllib.error, urllib.request
from urllib.parse import urlencode
from ..domain.errors import ProviderUnavailable
from ..domain.youtube import parse_iso_duration

def default_get(url: str, timeout: float):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

class YouTubeDataApi:
    """Somente YouTube Data API v3 (search.list e videos.list). A chave nunca vai ao navegador."""
    BASE = "https://www.googleapis.com/youtube/v3/"

    def __init__(self, api_key, http_get=default_get, timeout=8):
        self.key, self.http_get, self.timeout = api_key, http_get, timeout

    def _call(self, path, params):
        url = self.BASE + path + "?" + urlencode({**params, "key": self.key})
        try:
            status, body = self.http_get(url, self.timeout)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderUnavailable("sem_internet", "sem acesso ao YouTube (internet indisponivel?)")
        if status == 200:
            return json.loads(body)
        reason = ""
        try: reason = json.loads(body)["error"]["errors"][0]["reason"]
        except Exception: pass
        if status == 403 and reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            raise ProviderUnavailable("youtube_cota", "cota da YouTube Data API esgotada")
        raise ProviderUnavailable("youtube_erro", f"YouTube respondeu {status} ({reason or 'sem detalhe'}); verifique a chave e a API habilitada")

    def search(self, q):
        data = self._call("search", {"part": "snippet", "type": "video", "maxResults": 5, "q": q})
        ids = [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
        return self.details(ids)

    def details(self, ids):
        if not ids: return []
        data = self._call("videos", {"part": "snippet,contentDetails,status", "id": ",".join(ids)})
        by = {}
        for v in data.get("items", []):
            sn = v.get("snippet", {}); th = sn.get("thumbnails", {})
            by[v["id"]] = {
                "video_id": v["id"], "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                "thumbnail": (th.get("medium") or th.get("default") or {}).get("url"),
                "duration_s": parse_iso_duration(v.get("contentDetails", {}).get("duration")),
                "embeddable": v.get("status", {}).get("embeddable"),
            }
        return [by[i] for i in ids if i in by]
