"""Fluxo integrado de API/WebSocket com serviços externos e GPU simulados."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from karaoke.application.media import MediaInfo
from karaoke.config import Settings
from karaoke.domain.states import State
from karaoke.infrastructure import network as net
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.api import create_app
from karaoke.interfaces.worker import run_once

HOST = {"Authorization": "Bearer H"}
GUEST = {"Authorization": "Bearer G"}
WS_HEADERS = {"origin": "http://testserver:8000", "host": "testserver:8000"}


class Validator:
    def probe(self, path, ext):
        return MediaInfo(120, frozenset({ext}), "fake")


class VideoSearch:
    def search(self, query):
        return [{"video_id": "a" * 11, "title": "Canção", "channel": "Artista", "duration": 120}]

    def details(self, ids):
        return [{"video_id": ids[0], "title": "Canção", "channel": "Artista", "duration": 120}]


def new_app(data_dir):
    settings = Settings(data_dir=data_dir, host_token="H", guest_token="G",
                        min_free_mb=0, max_upload_mb=1)
    interfaces = lambda: net.classify([("Wi-Fi", "192.168.0.15")])
    app = create_app(settings, SqliteStore(settings.db_path), validator=Validator(),
                     ifaces_provider=interfaces, video_search=VideoSearch())
    return app, settings


class FakeProcessor:
    def __init__(self, settings):
        self.settings = settings

    def run(self, job, advance):
        d = self.settings.data_dir / "songs" / job.song_id
        advance(State.SEPARANDO_INSTRUMENTAL_VOCAIS, "fake")
        advance(State.SEPARANDO_LEAD_BACKING, "fake")
        advance(State.ANALISANDO, "fake")
        for stem in ("instrumental", "vocals", "lead", "backing"):
            (d / f"{stem}.wav").write_bytes(b"fake wav")
        (d / "processing.json").write_text(json.dumps({
            "schema": 1,
            "stems": ["instrumental.wav", "vocals.wav", "lead.wav", "backing.wav"],
            "lead_backing": {"available": True, "model": "fake-test-only"},
            "key": {"estimated": None, "confidence": 0, "warning": ""},
        }), encoding="utf-8")


def command(ws, kind, value=None):
    ws.send_json({"type": "command", "kind": kind, "value": value})
    event = ws.receive_json()
    assert event["type"] == "snapshot", event
    return event["state"]


def test_qr_search_upload_processing_lyrics_singing_and_restart(tmp_path):
    app, settings = new_app(tmp_path)
    client = TestClient(app)
    qr = client.get("/api/network/qr.svg", headers=HOST)
    assert qr.status_code == 200
    assert qr.headers["content-type"].startswith("image/svg+xml")
    search = client.get("/api/search", params={"q": "Canção"}, headers=GUEST)
    assert search.status_code == 200 and search.json()["items"]

    created = client.post("/api/songs", headers=GUEST,
                          json={"title": "Canção", "artist": "Artista", "source_video_id": "a" * 11})
    assert created.status_code == 201
    sid = created.json()["id"]
    uploaded = client.post(f"/api/songs/{sid}/upload", headers=HOST,
                           files={"file": ("original.mp3", b"audio de teste")})
    assert uploaded.status_code == 201
    store = SqliteStore(settings.db_path)
    assert run_once(store, FakeProcessor(settings))
    job = store.get_job(uploaded.json()["id"])
    assert job.state == State.CONCLUIDA, job.error

    lrc = b"[00:01.00]Primeira linha\n[00:03.00]Segunda linha\n"
    imported = client.post(f"/api/songs/{sid}/lyrics/import-lrc", headers=HOST,
                           files={"file": ("teste.lrc", lrc, "text/plain")})
    assert imported.status_code == 200, imported.text
    assert imported.json()["status"] == "LETRA_SINCRONIZADA"
    lyric = client.get(f"/api/songs/{sid}/lyrics", headers=GUEST).json()
    assert lyric["lines"][0] == [1000, "Primeira linha"]
    assert client.get("/api/songs", headers=GUEST).json()[0]["library"]["lead_backing_available"]
    for stem in ("instrumental", "lead", "backing"):
        assert client.get(f"/api/songs/{sid}/audio/{stem}", headers=HOST).status_code == 200

    with client.websocket_connect("/api/ws/live", headers=WS_HEADERS) as host:
        host.send_json({"type": "auth", "token": "H"})
        assert host.receive_json()["state"]["host_online"]
        with client.websocket_connect("/api/ws/live", headers=WS_HEADERS) as guest:
            guest.send_json({"type": "auth", "token": "G"})
            assert guest.receive_json()["state"]["host_online"]
            selected = command(host, "select", sid)
            assert selected["song_id"] == sid and not selected["playing"]
            assert guest.receive_json()["state"]["song_id"] == sid
            assert command(host, "ready")["host_ready"]
            assert guest.receive_json()["state"]["host_ready"]
            guest.send_json({"type": "command", "kind": "volume",
                             "value": {"stem": "backing", "level": 0.45}})
            assert guest.receive_json()["state"]["backing"] == 0.45
            assert host.receive_json()["state"]["backing"] == 0.45
            guest.send_json({"type": "command", "kind": "play"})
            assert guest.receive_json()["state"]["playing"]
            assert host.receive_json()["state"]["playing"]
            # Em caso de queda/reinício, o host não fica tocando automaticamente.
    restarted, _ = new_app(tmp_path)
    again = TestClient(restarted)
    assert again.get(f"/api/songs/{sid}/lyrics", headers=GUEST).json()["lines"][0][1] == "Primeira linha"
    assert again.get("/api/songs", headers=GUEST).json()[0]["library"]["lead_backing_available"]
    with again.websocket_connect("/api/ws/live", headers=WS_HEADERS) as guest:
        guest.send_json({"type": "auth", "token": "G"})
        state = guest.receive_json()["state"]
        assert state["song_id"] == sid
        assert state["playing"] is False
        assert state["host_ready"] is False
