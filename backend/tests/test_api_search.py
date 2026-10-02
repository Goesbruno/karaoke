from fastapi.testclient import TestClient
from karaoke.config import Settings
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

H, G = {"Authorization": "Bearer H"}, {"Authorization": "Bearer G"}

class Prov:
    def __init__(self): self.calls = []
    def search(self, q): self.calls.append("search"); return [{"video_id": "a" * 11, "title": "t"}]
    def details(self, ids): self.calls.append("details"); return [{"video_id": ids[0], "title": "t"}]

def client(tmp_path, prov):
    s = Settings(data_dir=tmp_path, host_token="H", guest_token="G")
    return TestClient(create_app(s, SqliteStore(s.db_path), video_search=prov))

def test_guest_can_search_text(tmp_path):
    r = client(tmp_path, Prov()).get("/api/search", params={"q": "queen"}, headers=G)
    assert r.status_code == 200 and r.json()["mode"] == "text" and r.json()["attribution"] == "YouTube"

def test_url_mode_and_invalid_url(tmp_path):
    p = Prov(); c = client(tmp_path, p)
    assert c.get("/api/search", params={"q": "https://youtu.be/dQw4w9WgXcQ"}, headers=G).json()["mode"] == "url"
    assert p.calls == ["details"]
    r = c.get("/api/search", params={"q": "https://evil.com/watch?v=dQw4w9WgXcQ"}, headers=G)
    assert r.status_code == 422 and r.json()["code"] == "url_invalida"

def test_auth_and_missing_key(tmp_path):
    c = client(tmp_path, None)
    assert c.get("/api/search", params={"q": "x"}).status_code == 401
    r = c.get("/api/search", params={"q": "x"}, headers=G)
    assert r.status_code == 503 and r.json()["code"] == "youtube_nao_configurado"

def test_song_rejects_bad_video_id(tmp_path):
    c = client(tmp_path, None)
    assert c.post("/api/songs", json={"title": "T", "source_video_id": "../x"}, headers=G).status_code == 422
    assert c.post("/api/songs", json={"title": "T", "source_video_id": "dQw4w9WgXcQ"}, headers=G).status_code == 201

def test_serves_frontend_when_built(tmp_path):
    d = tmp_path / "dist"; d.mkdir(); (d / "index.html").write_text("<h1>ok</h1>")
    s = Settings(data_dir=tmp_path / "d", host_token="H", guest_token="G", frontend_dist=d)
    c = TestClient(create_app(s, SqliteStore(s.db_path)))
    assert "ok" in c.get("/").text and c.get("/api/songs").status_code == 401
