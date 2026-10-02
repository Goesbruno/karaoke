from ..domain.errors import NotFound, ProviderUnavailable
from ..domain.youtube import looks_like_url, parse_youtube_url

class SearchService:
    def __init__(self, provider):
        self.provider = provider

    def run(self, q: str) -> dict:
        q = (q or "").strip()
        if not q or len(q) > 200:
            raise ValueError("informe um nome de musica ou URL (ate 200 caracteres)")
        if self.provider is None:
            raise ProviderUnavailable("youtube_nao_configurado", "YOUTUBE_API_KEY nao configurada no servidor")
        if looks_like_url(q):
            items = self.provider.details([parse_youtube_url(q)])
            if not items: raise NotFound("video nao encontrado ou indisponivel")
            return {"mode": "url", "attribution": "YouTube", "items": items}
        return {"mode": "text", "attribution": "YouTube", "items": self.provider.search(q)}
