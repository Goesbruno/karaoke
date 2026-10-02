import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from karaoke.config import Settings
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

HEAD={'origin':'http://testserver:8000','host':'testserver:8000'}

def test_auth_origin_and_guest_permissions(tmp_path):
    s=Settings(data_dir=tmp_path,host_token='H',guest_token='G');c=TestClient(create_app(s,SqliteStore(s.db_path)))
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/api/ws/live',headers={'origin':'http://evil:8000','host':'testserver:8000'}) as ws:pass
    with c.websocket_connect('/api/ws/live',headers=HEAD) as ws:
        ws.send_json({'type':'auth','token':'G'});snap=ws.receive_json()
        assert snap['type']=='snapshot' and snap['state']['host_online'] is False
        ws.send_json({'type':'command','kind':'background','value':'x'})
        assert ws.receive_json()['type']=='error'

def test_host_connected_and_guest_command(tmp_path):
    s=Settings(data_dir=tmp_path,host_token='H',guest_token='G');c=TestClient(create_app(s,SqliteStore(s.db_path)))
    with c.websocket_connect('/api/ws/live',headers=HEAD) as host:
        host.send_json({'type':'auth','token':'H'});assert host.receive_json()['state']['host_online']
        with c.websocket_connect('/api/ws/live',headers=HEAD) as guest:
            guest.send_json({'type':'auth','token':'G'});assert guest.receive_json()['state']['host_online']
            guest.send_json({'type':'command','kind':'play'});assert guest.receive_json()['type']=='error'
