from pathlib import Path
root=Path.cwd();src=root/'frontend/src';assert (src/'App.tsx').is_file(),'Rode na pasta karaoke'
patches=[('domain/types.ts', '  key_manual: string | null;', '  key_manual: string | null;\n  lyrics_offset_ms: number;'), ('ports/api.ts', '  importLrc(id: string, file: File): Promise<LyricsRecord>;', '  importLrc(id: string, file: File): Promise<LyricsRecord>;\n  updateLyricsOffset(id: string, offset_ms: number): Promise<{offset_ms: number}>;'), ('adapters/httpApi.ts', '  diagnostics() { return this.json<never>("/api/library/diagnostics"); }', '  diagnostics() { return this.json<never>("/api/library/diagnostics"); }\n  updateLyricsOffset(id: string, offset_ms: number) { return this.json<{offset_ms:number}>(`/api/songs/${encodeURIComponent(id)}/lyrics/offset`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({offset_ms})}); }'), ('App.tsx', 'import { LyricsPage } from "./features/LyricsPage";', 'import { LyricsPage } from "./features/LyricsPage";\nimport { KaraokePage } from "./features/KaraokePage";'), ('App.tsx', 'type Tab = "buscar" | "fila" | "biblioteca" | "letras" | "rede";', 'type Tab = "buscar" | "fila" | "biblioteca" | "letras" | "cantar" | "rede";'), ('App.tsx', '["buscar", "fila", "biblioteca", "letras", "rede"] : ["buscar", "fila", "biblioteca", "letras"]', '["buscar", "fila", "biblioteca", "letras", "cantar", "rede"] : ["buscar", "fila", "biblioteca", "letras", "cantar"]'), ('App.tsx', '      {tab === "rede" && isHost && <NetworkPanel api={api} />}', '      {tab === "cantar" && <KaraokePage api={api} songs={list} isHost={isHost} refresh={() => void songs.reload()} />}\n      {tab === "rede" && isHost && <NetworkPanel api={api} />}')]
staged={}
for rel,old,new in patches:
    p=src/rel;s=staged.get(p,p.read_text(encoding='utf-8'))
    if new in s:continue
    if s.count(old)!=1:raise RuntimeError(f'Arquivo mudou: {rel}: {old[:75]} (nenhuma alteracao feita)')
    staged[p]=s.replace(old,new)
style=src/'styles.css';st=style.read_text(encoding='utf-8')
if '.karaoke-stage {' not in st:staged[style]=st+'\n.karaoke-stage { position:relative; height: min(60vh,700px); overflow:auto; background-position:center; background-size:cover; border-radius:12px; padding:2rem; text-align:center; }\n.karaoke-stage:fullscreen { height:100vh; border-radius:0; display:grid; place-items:center; background-size:cover; }\n.karaoke-lines { margin:auto; font-size:clamp(1.5rem,3vw,3rem); text-shadow:0 2px 8px #000; }\n.karaoke-lines p { opacity:.4; transition:opacity .2s; }\n.karaoke-lines .karaoke-active { opacity:1; color:#ffdf66; font-weight:700; }\n.karaoke-exit { position:absolute; top:1rem;right:1rem; }\n'
for p,s in staged.items():p.write_text(s,encoding='utf-8')
pkg=Path(__file__).resolve().parent
for name in ['KaraokePage.tsx','syncedAudio.ts','syncedAudio.test.ts']:
    (src/'features'/name).write_bytes((pkg/'frontend/src/features'/name).read_bytes())
print('Frontend canto instalado; cd frontend; npm test; npm run build')
