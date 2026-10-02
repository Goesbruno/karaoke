import json
from pathlib import Path
from fastapi.testclient import TestClient
from karaoke.application.library_read import LibraryReader
from karaoke.config import Settings
from karaoke.infrastructure.local_files import LocalFileStore
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

H = {"Authorization": "Bearer host"}
G = {"Authorization": "Bearer guest"}

def fixture(tmp_path):
    s = Settings(data_dir=tmp_path, host_token="host", guest_token="guest")
    db = SqliteStore(s.db_path); files = LocalFileStore(tmp_path)
    item = db.create_song("Inicial", "Artista", None)
    d = files.song_dir(item.id); d.mkdir()
    db.set_file(item.id, "a"*64, 41.352, "a.mp3", "mp3")
    job = db.enqueue(item.id, 3); db.claim_next()
    from karaoke.domain.states import State
    db.advance(job.id, State.SEPARANDO_INSTRUMENTAL_VOCAIS)
    db.advance(job.id, State.ANALISANDO)
    db.advance(job.id, State.CONCLUIDA)
    (d / "original.mp3").write_bytes(b"a")
    (d / "instrumental.wav").write_bytes(b"i")
    (d / "vocals.wav").write_bytes(b"v")
    (d / "processing.json").write_text(json.dumps({"schema": 1, "stems": ["instrumental.wav", "vocals.wav"],
        "key": {"estimated": None, "confidence": 0.047, "warning": "tom inconclusivo"},
        "lead_backing": {"available": False, "reason": "sem modelo"}}), encoding="utf-8")
    return s,db,files,item,d

def test_persists_after_restart(tmp_path):
    s,db,files,item,d=fixture(tmp_path)
    c=TestClient(create_app(s,db,files=files)); x=c.get("/api/songs",headers=G).json()[0]
    assert x["library"]["ready"] and x["library"]["key_estimated"] is None
    assert x["library"]["key_confidence"] == 0.047
    assert c.patch(f"/api/songs/{item.id}",json={"title":"Novo", "artist":"Pessoa", "key_manual":"G maior"},headers=G).status_code == 403
    assert c.patch(f"/api/songs/{item.id}",json={"title":"Novo", "artist":"Pessoa", "key_manual":"G maior"},headers=H).status_code == 200
    db2=SqliteStore(s.db_path); c2=TestClient(create_app(s,db2,files=files))
    y=c2.get("/api/songs",headers=G).json()[0]
    assert y["title"] == "Novo" and y["artist"] == "Pessoa" and y["key_manual"] == "G maior" and y["library"]["ready"]
    assert c2.get(f"/api/songs/{item.id}/audio/instrumental",headers=G).content == b"i"
    assert c2.get(f"/api/songs/{item.id}/audio/original",headers=G).status_code == 404
    assert c2.get(f"/api/songs/{item.id}/audio/vocals").status_code == 401

def test_missing_stem_is_not_ready_and_does_not_delete(tmp_path):
    s,db,files,item,d=fixture(tmp_path)
    (d / "instrumental.wav").unlink()
    c=TestClient(create_app(s,db,files=files)); x=c.get("/api/songs",headers=G).json()[0]
    assert not x["library"]["ready"] and "instrumental.wav_ausente" in x["library"]["issues"]
    assert c.get(f"/api/songs/{item.id}/audio/instrumental",headers=G).status_code == 409
    assert (d / "original.mp3").exists() and (d / "vocals.wav").exists()

def test_invalid_manifest_no_audio(tmp_path):
    s,db,files,item,d=fixture(tmp_path)
    (d / "processing.json").write_text("{",encoding="utf-8")
    c=TestClient(create_app(s,db,files=files))
    assert "processing_json_invalido" in c.get("/api/songs",headers=G).json()[0]["library"]["issues"]
    assert c.get(f"/api/songs/{item.id}/audio/vocals",headers=G).status_code == 409

def test_migration_from_v2(tmp_path):
    import sqlite3
    from karaoke.infrastructure.sqlite_store import V1,V2
    p=tmp_path/"db.sqlite"; c=sqlite3.connect(p); c.executescript(V1); c.executescript(V2)
    c.execute("PRAGMA user_version=2");c.execute("INSERT INTO songs(id,title,artist,status,created_at) VALUES('x','Antiga','','AGUARDANDO_UPLOAD','now')");c.commit();c.close()
    db=SqliteStore(p)
    assert db.manual_key('x') is None and db.get_song('x').title == 'Antiga'
    assert db.db.execute("PRAGMA user_version").fetchone()[0] == 4
