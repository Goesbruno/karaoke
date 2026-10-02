import pytest
from fastapi.testclient import TestClient
from karaoke.config import Settings
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app

@pytest.fixture
def ctx(tmp_path):
    s = Settings(data_dir=tmp_path, host_token="H", guest_token="G")
    return TestClient(create_app(s, SqliteStore(s.db_path))), {"Authorization": "Bearer H"}, {"Authorization": "Bearer G"}

def test_no_token_401(ctx):
    c, h, g = ctx
    assert c.get("/api/songs").status_code == 401
    assert c.get("/api/songs", headers={"Authorization": "Bearer x"}).status_code == 401

def test_join_roles(ctx):
    c, *_ = ctx
    assert c.post("/api/session/join", json={"token": "H"}).json()["role"] == "host"
    assert c.post("/api/session/join", json={"token": "G"}).json()["role"] == "guest"
    assert c.post("/api/session/join", json={"token": "?"}).status_code == 401

def test_guest_cannot_admin(ctx):
    c, h, g = ctx
    sid = c.post("/api/songs", json={"title": "T"}, headers=g).json()["id"]
    assert c.post(f"/api/songs/{sid}/enqueue", headers=g).status_code == 403
    assert c.post(f"/api/songs/{sid}/enqueue", headers=h).status_code == 201

def test_queue_position_and_cancel(ctx):
    c, h, g = ctx
    ids = [c.post("/api/songs", json={"title": f"T{i}"}, headers=g).json()["id"] for i in range(2)]
    for i in ids: c.post(f"/api/songs/{i}/enqueue", headers=h)
    jobs = c.get("/api/jobs", headers=g).json()
    assert [j["position"] for j in jobs] == [1, 2]
    assert c.post(f"/api/jobs/{jobs[0]['id']}/cancel", headers=g).status_code == 403
    assert c.post(f"/api/jobs/{jobs[0]['id']}/cancel", headers=h).json()["state"] == "CANCELADA"

def test_validation_and_conflicts(ctx):
    c, h, g = ctx
    assert c.post("/api/songs", json={"title": "  "}, headers=g).status_code == 422
    sid = c.post("/api/songs", json={"title": "T"}, headers=g).json()["id"]
    c.post(f"/api/songs/{sid}/enqueue", headers=h)
    assert c.post(f"/api/songs/{sid}/enqueue", headers=h).status_code == 409
    assert c.post("/api/songs/nope/enqueue", headers=h).status_code == 404

def test_configurable_roles(tmp_path):
    s = Settings(data_dir=tmp_path, host_token="H", guest_token="G", roles={"host": ["songs:read"], "guest": []})
    c = TestClient(create_app(s, SqliteStore(s.db_path)))
    assert c.get("/api/songs", headers={"Authorization": "Bearer G"}).status_code == 403
