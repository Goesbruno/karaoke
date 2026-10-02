from pathlib import Path
import ast
root=Path.cwd();pkg=Path(__file__).resolve().parent
api=root/'backend/src/karaoke/interfaces/api.py';cfg=root/'backend/src/karaoke/config.py'
assert api.is_file() and cfg.is_file(),'Execute na raiz karaoke'
a=api.read_text(encoding='utf-8');c=cfg.read_text(encoding='utf-8')
if 'LiveHub(' not in a:
    for old,new in [('from .auth import Authenticator', 'from ..application.live_session import LiveSession\nfrom .live_ws import LiveHub\nfrom .auth import Authenticator'), ('    store.recover()', '    live_hub = LiveHub(LiveSession(store, files=files), auth, settings.port)\n    store.recover()'), ('    dist = Path(settings.frontend_dist)', '    @app.websocket("/api/ws/live")\n    async def live_socket(websocket: WebSocket):\n        await live_hub.handle(websocket)\n\n    dist = Path(settings.frontend_dist)'), ('from fastapi import Depends, FastAPI, File, HTTPException, UploadFile', 'from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket')]:
        if a.count(old)!=1:raise RuntimeError('API difere do esperado: '+old[:60]+'; nada alterado')
        a=a.replace(old,new)
if '"session:control"' not in c:
    # Inserção limitada às permissões padrão; permissões personalizadas em .env devem ser ajustadas separadamente.
    import re
    c,h=re.subn(r'("host":\s*\[[^\]]*)\]',lambda m:m.group(1)+', "session:control", "session:manage"]',c,count=1)
    c,g=re.subn(r'("guest":\s*\[[^\]]*)\]',lambda m:m.group(1)+', "session:control"]',c,count=1)
    if h!=1 or g!=1:raise RuntimeError('Papeis inesperados; nada alterado')
ast.parse(a);ast.parse(c)
for rel in ['application/live_session.py','interfaces/live_ws.py']:
    dst=root/'backend/src/karaoke'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_bytes((pkg/'backend/src/karaoke'/rel).read_bytes())
for name in ['test_live_session.py','test_live_ws.py']:
    (root/'backend/tests'/name).write_bytes((pkg/'backend/tests'/name).read_bytes())
api.write_text(a,encoding='utf-8');cfg.write_text(c,encoding='utf-8')
print('Sessao backend instalada; uv run pytest backend/tests/test_live_session.py backend/tests/test_live_ws.py')
