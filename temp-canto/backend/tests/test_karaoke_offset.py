from fastapi.testclient import TestClient
from karaoke.config import Settings
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

def test_offset_persists_and_requires_host(tmp_path):
    s=Settings(data_dir=tmp_path,host_token="H",guest_token="G")
    db=SqliteStore(s.db_path);song=db.create_song("T","A",None)
    c=TestClient(create_app(s,db))
    path=f"/api/songs/{song.id}/lyrics/offset"
    H={"Authorization":"Bearer H"};G={"Authorization":"Bearer G"}
    assert c.patch(path,headers=G,json={"offset_ms":300}).status_code==403
    assert c.patch(path,headers=H,json={"offset_ms":10001}).status_code==422
    assert c.patch(path,headers=H,json={"offset_ms":-250}).json()=={"offset_ms":-250}
    assert c.get("/api/songs",headers=G).json()[0]["lyrics_offset_ms"]==-250
    db2=SqliteStore(s.db_path);c2=TestClient(create_app(s,db2))
    assert c2.get("/api/songs",headers=G).json()[0]["lyrics_offset_ms"]==-250

def test_v3_migration_preserves_song(tmp_path):
    from karaoke.infrastructure.sqlite_store import V1,V2,V3
    import sqlite3
    p=tmp_path/'old.db';c=sqlite3.connect(p)
    c.executescript(V1);c.executescript(V2);c.executescript(V3)
    c.execute('PRAGMA user_version=3');c.execute("INSERT INTO songs(id,title,artist,status,created_at) VALUES('id','Antiga','','AGUARDANDO_UPLOAD','now')")
    c.commit();c.close()
    db=SqliteStore(p)
    assert db.get_song('id').title=='Antiga' and db.lyrics_offset('id')==0
    assert db.db.execute('PRAGMA user_version').fetchone()[0]==4
