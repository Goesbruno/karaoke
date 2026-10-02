from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from karaoke.application.live_session import LiveSession, SessionError
from karaoke.config import Settings
from karaoke.infrastructure.song_backgrounds import SongBackgrounds
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

H, G = {"Authorization": "Bearer H"}, {"Authorization": "Bearer G"}
PNG_A = b"\x89PNG\r\n\x1a\n" + b"A" * 40
PNG_B = b"\x89PNG\r\n\x1a\n" + b"B" * 40


@pytest.fixture
def client(tmp_path):
    s = Settings(data_dir=tmp_path, host_token="H", guest_token="G")
    return TestClient(create_app(s, SqliteStore(s.db_path)))


def new_song(c):
    return c.post("/api/songs", json={"title": "T", "artist": "A"}, headers=G).json()["id"]


def put(c, sid, data=PNG_A, headers=H, name="bg.png"):
    return c.put(f"/api/songs/{sid}/background", files={"file": (name, data, "image/png")}, headers=headers)


def test_host_saves_lists_and_removes(client):
    sid = new_song(client)
    assert put(client, sid).status_code == 200
    assert client.get("/api/backgrounds", headers=G).json() == {"song_ids": [sid]}
    assert client.delete(f"/api/songs/{sid}/background", headers=H).json() == {"has_background": False}
    assert client.get("/api/backgrounds", headers=H).json() == {"song_ids": []}


def test_permissions_and_validation(client):
    sid = new_song(client)
    assert put(client, sid, headers=G).status_code == 403
    assert client.put(f"/api/songs/{sid}/background", files={"file": ("a.png", PNG_A)}).status_code == 401
    assert put(client, sid, b"nao e imagem, apenas texto").status_code == 422
    assert put(client, sid, PNG_A + b"x" * 300_000).status_code == 422
    assert put(client, "11111111-1111-4111-8111-111111111111").status_code == 404


def make_session(tmp_path, monkeypatch):
    db = SqliteStore(tmp_path / "live.db")
    monkeypatch.setattr("karaoke.application.library_read.LibraryReader",
                        lambda files: NS(read=lambda song: NS(ready=True)))
    monkeypatch.setattr("karaoke.infrastructure.lyrics_store.get", lambda store, sid: {"status": "LETRA_SINCRONIZADA"})
    songs = [db.create_song(t, "A", None) for t in ("Um", "Dois", "Tres")]
    for s in songs:
        db.db.execute("UPDATE songs SET status='CONCLUIDA' WHERE id=?", (s.id,))
    return db, LiveSession(db, lambda: 1000, files=object()), songs


def test_each_song_selects_its_own_background(tmp_path, monkeypatch):
    db, live, (a, b, c) = make_session(tmp_path, monkeypatch)
    bg = SongBackgrounds(db)
    bg.set(a.id, PNG_A)
    bg.set(b.id, PNG_B)
    assert live.command("host", "select", a.id)["background"] == bg.get(a.id) != ""
    assert live.command("host", "select", b.id)["background"] == bg.get(b.id) != bg.get(a.id)
    assert live.command("host", "select", c.id)["background"] == ""
    assert live.command("host", "select", a.id)["background"] == bg.get(a.id)


def test_background_reload_is_host_only_and_follows_current_song(tmp_path, monkeypatch):
    db, live, (a, b, c) = make_session(tmp_path, monkeypatch)
    live.command("host", "select", a.id)
    SongBackgrounds(db).set(a.id, PNG_A)
    with pytest.raises(SessionError):
        live.command("guest", "background_reload")
    assert live.command("host", "background_reload")["background"].startswith("data:image/png;base64,")
    SongBackgrounds(db).clear(a.id)
    assert live.command("host", "background_reload")["background"] == ""


def test_deleting_song_removes_its_background(tmp_path, monkeypatch):
    db, live, (a, b, c) = make_session(tmp_path, monkeypatch)
    bg = SongBackgrounds(db)
    bg.set(a.id, PNG_A)
    db.delete_song(a.id)
    assert bg.ids() == []
