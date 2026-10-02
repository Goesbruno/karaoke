import asyncio,json
from fastapi import WebSocket,WebSocketDisconnect
from ..application.live_session import LiveSession,SessionError

class LiveHub:
    def __init__(self,session:LiveSession,auth,port:int):
        self.session=session;self.auth=auth;self.port=port
        self.clients:set[WebSocket]=set();self.host:WebSocket|None=None;self.lock=asyncio.Lock()

    async def broadcast(self,payload):
        dead=[]
        for ws in list(self.clients):
            try:await ws.send_json(payload)
            except Exception:dead.append(ws)
        for ws in dead:self.clients.discard(ws)

    async def handle(self,ws:WebSocket):
        origin=ws.headers.get('origin','');host=ws.headers.get('host','')
        if not host or origin not in (f'http://{host}',f'https://{host}') or host.rsplit(':',1)[-1]!=str(self.port):
            await ws.close(code=4403);return
        await ws.accept()
        try:
            hello=await asyncio.wait_for(ws.receive_json(),timeout=5)
            if hello.get('type')!='auth':raise SessionError('autenticação obrigatória')
            role=self.auth.role_of(hello.get('token'))
            if not role:raise SessionError('token inválido')
        except (asyncio.TimeoutError,ValueError,AttributeError,WebSocketDisconnect):
            await ws.close(code=4401);return
        async with self.lock:
            if role=='host' and self.host is not None:
                await ws.close(code=4409);return
            self.clients.add(ws)
            if role=='host':
                self.host=ws;snap=self.session.host(True)
                await self.broadcast({'type':'snapshot','state':snap})
            else:await ws.send_json({'type':'snapshot','state':self.session.snapshot()})
        try:
            while True:
                msg=await ws.receive_json()
                if msg.get('type')=='sync':
                    await ws.send_json({'type':'clock','nonce':msg.get('nonce'),'server_ms':self.session.clock()});continue
                if msg.get('type')!='command':continue
                async with self.lock:
                    try:
                        permission = 'session:manage' if msg.get('kind') in ('select','ready','background','offset','report') else 'session:control'
                        if permission not in self.auth.roles.get(role,[]):
                            raise SessionError('permissão insuficiente')
                        snap=self.session.command(role,msg.get('kind'),msg.get('value'))
                    except (SessionError,ValueError,TypeError) as e:
                        await ws.send_json({'type':'error','message':str(e)});continue
                    await self.broadcast({'type':'snapshot','state':snap})
        except (WebSocketDisconnect,RuntimeError,ValueError):pass
        finally:
            async with self.lock:
                self.clients.discard(ws)
                if self.host is ws:
                    self.host=None
                    await self.broadcast({'type':'snapshot','state':self.session.host(False)})
