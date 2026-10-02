from pathlib import Path
root=Path.cwd();p=root/'frontend/src/App.tsx';assert p.is_file(),'Execute na raiz karaoke'
s=p.read_text(encoding='utf-8')
if 'LiveRoom' not in s:
    for old,new in [('import { KaraokePage } from "./features/KaraokePage";', 'import { LiveRoom } from "./features/LiveRoom";'), ('      {tab === "cantar" && <KaraokePage api={api} songs={list} isHost={isHost} refresh={() => void songs.reload()} />}', '      {tab === "cantar" && <LiveRoom api={api} songs={list} isHost={isHost} />}')]:
        if s.count(old)!=1:raise RuntimeError('App.tsx diferente do esperado: '+old[:80]+'; nenhuma alteração feita')
        s=s.replace(old,new)
pkg=Path(__file__).resolve().parent
for name in ['LiveRoom.tsx','liveClock.ts','liveClock.test.ts']:
    (root/'frontend/src/features'/name).write_bytes((pkg/'frontend/src/features'/name).read_bytes())
p.write_text(s,encoding='utf-8')
print('Frontend sessão instalado; cd frontend; npm test; npm run build')
