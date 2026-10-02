import pytest
from fastapi.testclient import TestClient
from karaoke.application.media import MediaInfo
from karaoke.config import Settings
from karaoke.infrastructure import network as net
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

class Val:
    def probe(self, path, ext): return MediaInfo(120, frozenset({ext}), "x")

H, G = {"Authorization": "Bearer H"}, {"Authorization": "Bearer G"}

@pytest.fixture
def c(tmp_path):
    s = Settings(data_dir=tmp_path, host_token="H", guest_token="G", min_free_mb=0, max_upload_mb=1)
    prov = lambda: net.classify([("Wi-Fi", "192.168.0.15"), ("Loopback", "127.0.0.1")])
    return TestClient(create_app(s, SqliteStore(s.db_path), validator=Val(), ifaces_provider=prov))

def new(c): return c.post("/api/songs", json={"title": "T", "artist": "A"}, headers=G).json()["id"]

def test_upload_host_only_and_queue(c):
    sid = new(c)
    assert c.post(f"/api/songs/{sid}/upload", files={"file": ("a.mp3", b"abc")}, headers=G).status_code == 403
    assert c.post(f"/api/songs/{sid}/upload", files={"file": ("a.mp3", b"abc")}).status_code == 401
    r = c.post(f"/api/songs/{sid}/upload", files={"file": ("a.mp3", b"abc")}, headers=H)
    assert r.status_code == 201 and r.json()["state"] == "NA_FILA" and r.json()["position"] == 1

def test_upload_errors(c):
    sid = new(c)
    r = c.post(f"/api/songs/{sid}/upload", files={"file": ("a.exe", b"abc")}, headers=H)
    assert r.status_code == 422 and r.json()["code"] == "extensao"
    r = c.post(f"/api/songs/{sid}/upload", files={"file": ("a.mp3", b"x" * 2_000_000)}, headers=H)
    assert r.json()["code"] == "tamanho"

def test_duplicate_409(c):
    a, b = new(c), c.post("/api/songs", json={"title": "Outra"}, headers=G).json()["id"]
    c.post(f"/api/songs/{a}/upload", files={"file": ("a.mp3", b"same")}, headers=H)
    r = c.post(f"/api/songs/{b}/upload", files={"file": ("a.mp3", b"same")}, headers=H)
    assert r.status_code == 409 and r.json()["existing_id"] == a

def test_delete_requires_host_and_confirmation(c):
    sid = new(c); c.post(f"/api/songs/{sid}/upload", files={"file": ("a.mp3", b"abc")}, headers=H)
    jid = c.get("/api/jobs", headers=H).json()[0]["id"]; c.post(f"/api/jobs/{jid}/cancel", headers=H)
    assert c.delete(f"/api/songs/{sid}?confirm=true", headers=G).status_code == 403
    assert c.delete(f"/api/songs/{sid}", headers=H).status_code == 400
    assert c.delete(f"/api/songs/{sid}?confirm=true", headers=H).json()["files_removed"] is True
    assert c.get("/api/songs", headers=H).json() == []

def test_network_and_qr(c):
    n = c.get("/api/network", headers=H).json()
    assert n["url"] == "http://192.168.0.15:8000/" and "127.0.0.1" not in str(n["interfaces"])
    assert "LRCLIB" in str(n["internet_dependencies"])
    assert c.get("/api/network", headers=G).status_code == 403

def test_diagnostics_host_only(c):
    assert c.get("/api/library/diagnostics", headers=G).status_code == 403
    assert "songs" in c.get("/api/library/diagnostics", headers=H).json()
