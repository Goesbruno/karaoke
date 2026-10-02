from pathlib import Path
import ast
root=Path.cwd(); pkg=Path(__file__).resolve().parent
base=root/'backend/src/karaoke'
api=base/'interfaces/api.py'; cfg=base/'config.py'
assert api.is_file() and cfg.is_file(), 'Execute na raiz da pasta karaoke'
a=api.read_text(encoding='utf-8');c=cfg.read_text(encoding='utf-8')

def replace_once(s,old,new):
    if s.count(old)!=1:raise RuntimeError('Trecho nao encontrado unicamente: '+old[:80])
    return s.replace(old,new)

if 'def lyric_suggestions(' not in a:
    a=replace_once(a,'from .auth import Authenticator','from ..application.lyrics import LyricsService\nfrom ..domain.lrc import InvalidLRC\nfrom ..infrastructure.lyrics_store import LyricsRepository\nfrom ..infrastructure.lrclib_client import LrclibProvider, LyricsProviderError\n'+'from .auth import Authenticator')
    a=replace_once(a,'    store.recover()','    lyrics_repo = LyricsRepository(store)\n    lyrics_service = LyricsService(lyrics_repo, LrclibProvider(settings.lrclib_client_id))\n'+'    store.recover()')
    a=replace_once(a,'    @app.exception_handler(ValueError)','    @app.exception_handler(InvalidLRC)\n    def _bad_lrc(_, e): return _json(422, {"detail":str(e)})\n    @app.exception_handler(LyricsProviderError)\n    def _provider_err(_, e):\n        from fastapi.responses import JSONResponse\n        return JSONResponse({"detail":str(e)},status_code=429 if e.retry_after else 503,\n                            headers={"Retry-After":str(e.retry_after)} if e.retry_after else {})\n'+'    @app.exception_handler(ValueError)')
    a=replace_once(a,'    dist = Path(settings.frontend_dist)','    @app.get("/api/songs/{song_id}/lyrics/suggestions")\n    def lyric_suggestions(song_id: str, _=Depends(auth.require("lyrics:search"))):\n        return lyrics_service.search(song_id)\n\n    @app.get("/api/songs/{song_id}/lyrics")\n    def selected_lyrics(song_id: str, _=Depends(auth.require("lyrics:read"))):\n        return lyrics_repo.get_lyrics(song_id)\n\n    @app.put("/api/songs/{song_id}/lyrics/lrclib/{record_id}")\n    def select_lyrics(song_id: str, record_id: int, _=Depends(auth.require("lyrics:choose"))):\n        return lyrics_service.choose(song_id,record_id)\n\n    @app.post("/api/songs/{song_id}/lyrics/import-lrc")\n    async def import_lrc(song_id: str, file: UploadFile = File(...), _=Depends(auth.require("lyrics:choose"))):\n        if not file.filename or not file.filename.lower().endswith(\'.lrc\'):\n            raise HTTPException(422,\'Somente arquivos .lrc\')\n        raw=await file.read(256001)\n        if len(raw)>256000:raise HTTPException(413,\'Arquivo .lrc excede 256 KB\')\n        try: text=raw.decode(\'utf-8-sig\')\n        except UnicodeDecodeError:raise HTTPException(422,\'LRC deve estar em UTF-8\')\n        return lyrics_service.import_lrc(song_id,text)\n\n'+'    dist = Path(settings.frontend_dist)')
if 'lrclib_client_id:' not in c:
    c=replace_once(c,'    ffprobe_path: str = "ffprobe"','    ffprobe_path: str = "ffprobe"\n    lrclib_client_id: str = "KaraokeLAN/0.6 (admin@example.org)"')
    c=replace_once(c,'            ffprobe_path=e.get("KARAOKE_FFPROBE_PATH", "ffprobe"),','            ffprobe_path=e.get("KARAOKE_FFPROBE_PATH", "ffprobe"),\n            lrclib_client_id=e.get("KARAOKE_LRCLIB_CLIENT_ID", "KaraokeLAN/0.6 (admin@example.org)"),')
if '"lyrics:choose"' not in c:
    import re

    c, host_count = re.subn(
        r'("host":\s*\[[^\]]*?"search:read")',
        r'\1, "lyrics:search", "lyrics:read", "lyrics:choose"',
        c,
        count=1,
    )
    c, guest_count = re.subn(
        r'("guest":\s*\[[^\]]*?"search:read")',
        r'\1, "lyrics:search", "lyrics:read"',
        c,
        count=1,
    )
    if host_count != 1 or guest_count != 1:
        raise RuntimeError(
            "Não foi possível localizar os papéis host e guest; nenhuma mudança salva"
        )
ast.parse(a);ast.parse(c)
for rel in ['domain/lrc.py','application/lyrics.py','infrastructure/lyrics_store.py','infrastructure/lrclib_client.py']:
    dest=base/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes((pkg/'backend/src/karaoke'/rel).read_bytes())
dest=root/'backend/tests/test_lyrics_module.py';dest.write_bytes((pkg/'backend/tests/test_lyrics_module.py').read_bytes())
api.write_text(a,encoding='utf-8');cfg.write_text(c,encoding='utf-8')
print('Instalacao concluida; rode uv run pytest backend/tests/test_lyrics_module.py')
