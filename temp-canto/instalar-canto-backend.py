from pathlib import Path
import ast
root=Path.cwd();assert (root/'backend/src/karaoke/interfaces/api.py').is_file(),'Rode na pasta karaoke'
patches=[('backend/src/karaoke/infrastructure/sqlite_store.py', 'MIGRATIONS = [V1, V2, V3]', 'V4 = """\nBEGIN;\nALTER TABLE songs ADD COLUMN lyrics_offset_ms INTEGER NOT NULL DEFAULT 0;\nCOMMIT;\n"""\nMIGRATIONS = [V1, V2, V3, V4]'), ('backend/src/karaoke/infrastructure/sqlite_store.py', '    def find_by_sha(self, sha):', '    def lyrics_offset(self, song_id):\n        with self.lock:\n            r=self.db.execute("SELECT lyrics_offset_ms FROM songs WHERE id=?",(song_id,)).fetchone()\n        if r is None: raise NotFound(song_id)\n        return r["lyrics_offset_ms"]\n\n    def set_lyrics_offset(self, song_id, ms):\n        if not isinstance(ms,int) or not -10000 <= ms <= 10000:\n            raise ValueError("offset deve estar entre -10000 e +10000 ms")\n        with self._tx() as c:\n            r=c.execute("UPDATE songs SET lyrics_offset_ms=? WHERE id=?",(ms,song_id))\n            if not r.rowcount: raise NotFound(song_id)\n        return ms\n\n    def find_by_sha(self, sha):'), ('backend/src/karaoke/interfaces/api.py', 'def _json(code, body):', 'class OffsetIn(BaseModel):\n    offset_ms: int = Field(ge=-10000, le=10000)\n\ndef _json(code, body):'), ('backend/src/karaoke/interfaces/api.py', '    @app.get("/api/songs/{song_id}/lyrics/suggestions")', '    @app.patch("/api/songs/{song_id}/lyrics/offset")\n    def update_lyrics_offset(song_id: str, body: OffsetIn, _=Depends(auth.require("lyrics:choose"))):\n        return {"offset_ms":store.set_lyrics_offset(song_id,body.offset_ms)}\n\n    @app.get("/api/songs/{song_id}/lyrics/suggestions")'), ('backend/src/karaoke/interfaces/api.py', '"key_manual": store.manual_key(s.id),', '"key_manual": store.manual_key(s.id), "lyrics_offset_ms":store.lyrics_offset(s.id),')]
staged={}
for rel,old,new in patches:
    p=root/rel;s=staged.get(p,p.read_text(encoding='utf-8'))
    if new in s:continue
    if s.count(old)!=1:raise RuntimeError(f'Arquivo mudou: {rel}: {old[:80]}; nada foi alterado')
    staged[p]=s.replace(old,new)
# Atualiza somente expectativas de versão dos testes legados (3 -> 4).
for name in ['test_network_ffprobe_migration.py','test_library_persistence.py']:
    t=root/'backend/tests'/name
    if t.is_file():
        old=t.read_text(encoding='utf-8')
        new=old.replace('assert st.db.execute("PRAGMA user_version").fetchone()[0] == 3',
                        'assert st.db.execute("PRAGMA user_version").fetchone()[0] == 4')
        new=new.replace('assert db.db.execute("PRAGMA user_version").fetchone()[0] == 3',
                        'assert db.db.execute("PRAGMA user_version").fetchone()[0] == 4')
        if new!=old:staged[t]=new
for p,s in staged.items():ast.parse(s)
for p,s in staged.items():p.write_text(s,encoding='utf-8')
(root/'backend/tests/test_karaoke_offset.py').write_bytes((Path(__file__).resolve().parent/'backend/tests/test_karaoke_offset.py').read_bytes())
print('Backend canto aplicado; rode uv run pytest backend/tests/test_karaoke_offset.py; uv run pytest')
