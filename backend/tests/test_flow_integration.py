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

H = {"Authorization": "Bearer H"}
G = {"Authorization": "Bearer G"}


class Validator:
    def probe(self, path, ext):
        return MediaInfo(120, frozenset({ext}), "test")


class SearchProvider:
    def search(self, q):
        return [{"video_id": "a" * 11, "title": "Teste", "channel": "Canal", "duration": 120}]

    def details(self, ids):
        return [{"video_id": ids[0], "title": "Teste", "channel": "Canal", "duration": 120}]


def make_app(tmp_path):
    settings = Settings(data_dir=tmp_path, host_token="H", guest_token="G",
                        min_free_mb=0, max_upload_mb=1)
    provider = lambda: net.classify([("Wi-Fi", "192.168.0.15")])
    app = create_app(settings, SqliteStore(settings.db_path),
                     validator=Validator(), ifaces_provider=provider,
                     video_search=SearchProvider())
    return app, settings


def test_qr_search_upload_processing_and_restart(tmp_path):
    app, settings = make_app(tmp_path)
    client = TestClient(app)
    qr = client.get("/api/network/qr.svg", headers=H)
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")
    search = client.get("/api/search", params={"q": "teste"}, headers=G)
    assert search.status_code == 200 and search.json()["items"]
    sid = client.post("/api/songs", json={"title": "Teste", "artist": "Artista",
                                           "source_video_id": "a" * 11}, headers=G).json()["id"]
    upload = client.post(f"/api/songs/{sid}/upload",
                         files={"file": ("teste.mp3", b"audio autorizado")}, headers=H)
    assert upload.status_code == 201
    store = SqliteStore(settings.db_path)

    class Processor:
        def run(self, job, advance):
            assert job.song_id == sid
            d = Path(settings.data_dir) / "songs" / sid
            for name in ("instrumental.wav", "vocals.wav", "lead.wav", "backing.wav"):
                (d / name).write_bytes(b"wav")
            (d / "processing.json").write_text(json.dumps({
                "schema": 1,
                "stems": ["instrumental.wav", "vocals.wav", "lead.wav", "backing.wav"],
                "lead_backing": {"available": True},
                "key": {"estimated": None, "confidence": 0, "warning": ""},
            }), encoding="utf-8")
            advance(State.SEPARANDO_INSTRUMENTAL_VOCAIS, "separacao simulada")
            advance(State.SEPARANDO_LEAD_BACKING, "backing simulado")
            advance(State.ANALISANDO, "analise simulada")

    assert run_once(store, Processor())
    job = store.list_jobs()[0]
    assert job.state == State.CONCLUIDA, f"Trabalho falhou: {job.error}"
    songs = client.get("/api/songs", headers=G).json()
    assert songs[0]["library"]["lead_backing_available"] is True
    for stem in ("instrumental", "vocals", "lead", "backing"):
        response = client.get(f"/api/songs/{sid}/audio/{stem}", headers=H)
        assert response.status_code == 200

    restarted, _ = make_app(tmp_path)
    restarted_client = TestClient(restarted)
    library = restarted_client.get("/api/songs", headers=G).json()[0]["library"]
    assert library["lead_backing_available"] is True
