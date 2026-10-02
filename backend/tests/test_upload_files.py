import pytest
from karaoke.application.library_ops import ReconcileService, DeletionService, UploadService, safe_display_name
from karaoke.application.media import MediaInfo
from karaoke.config import Settings
from karaoke.domain.errors import Conflict, Duplicate, UploadRejected
from karaoke.domain.states import State
from karaoke.infrastructure.local_files import LocalFileStore
from karaoke.infrastructure.sqlite_store import SqliteStore

class FakeVal:
    def __init__(self, dur=120): self.dur = dur; self.err = None
    def probe(self, path, ext):
        if self.err: raise self.err
        return MediaInfo(self.dur, frozenset({ext}), "x")

@pytest.fixture
def env(tmp_path):
    s = Settings(data_dir=tmp_path, max_upload_mb=1, min_free_mb=0)
    st, fs, v = SqliteStore(":memory:"), LocalFileStore(tmp_path), FakeVal()
    return s, st, fs, v, UploadService(st, fs, v, s)

def chunks(b): yield b

def song(st, t="T", a="A"): return st.create_song(t, a, None)

def test_happy_path(env):
    s, st, fs, v, up = env; sg = song(st)
    j = up.upload(sg.id, chunks(b"abc" * 100), "musica.MP3")
    assert j.state == State.NA_FILA
    assert fs.list_files(sg.id) == ["original.mp3"]
    g = st.get_song(sg.id)
    assert g.sha256 and g.ext == "mp3" and g.duration_s == 120

def test_bad_extension_and_cleanup(env):
    s, st, fs, v, up = env; sg = song(st)
    with pytest.raises(UploadRejected) as e: up.upload(sg.id, chunks(b"x"), "a.exe")
    assert e.value.code == "extensao" and fs.list_files(sg.id) == []

def test_too_large(env):
    s, st, fs, v, up = env; sg = song(st)
    with pytest.raises(UploadRejected) as e: up.upload(sg.id, chunks(b"x" * (2 * 1024 * 1024)), "a.mp3")
    assert e.value.code == "tamanho" and fs.list_files(sg.id) == []

def test_empty(env):
    s, st, fs, v, up = env; sg = song(st)
    with pytest.raises(UploadRejected) as e: up.upload(sg.id, chunks(b""), "a.mp3")
    assert e.value.code == "vazio"

def test_validator_rejection_cleans(env):
    s, st, fs, v, up = env; sg = song(st); v.err = UploadRejected("conteudo_invalido", "x")
    with pytest.raises(UploadRejected): up.upload(sg.id, chunks(b"x"), "a.mp3")
    assert fs.list_files(sg.id) == [] and st.get_song(sg.id).status == State.AGUARDANDO_UPLOAD

@pytest.mark.parametrize("dur", [5, 99999])
def test_duration_bounds(env, dur):
    s, st, fs, v, up = env; sg = song(st); v.dur = dur
    with pytest.raises(UploadRejected) as e: up.upload(sg.id, chunks(b"x"), "a.mp3")
    assert e.value.code == "duracao"

def test_disk_space(env, monkeypatch):
    s, st, fs, v, up = env; sg = song(st)
    monkeypatch.setattr(fs, "free_bytes", lambda: 0)
    with pytest.raises(UploadRejected) as e: up.upload(sg.id, chunks(b"x"), "a.mp3")
    assert e.value.code == "espaco"

def test_duplicate_hash(env):
    s, st, fs, v, up = env; a, b = song(st, "A1"), song(st, "B1")
    up.upload(a.id, chunks(b"same"), "a.mp3")
    with pytest.raises(Duplicate) as e: up.upload(b.id, chunks(b"same"), "b.mp3")
    assert e.value.code == "duplicado" and e.value.existing_id == a.id
    assert fs.list_files(b.id) == []

def test_homonym_needs_admin_decision(env):
    s, st, fs, v, up = env; a, b = song(st), song(st)
    up.upload(a.id, chunks(b"one"), "a.mp3")
    with pytest.raises(Duplicate) as e: up.upload(b.id, chunks(b"two"), "b.mp3")
    assert e.value.code == "homonimo"
    up.upload(b.id, chunks(b"two"), "b.mp3", allow_homonym=True)

def test_upload_only_when_waiting(env):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3")
    with pytest.raises(Conflict): up.upload(sg.id, chunks(b"y"), "a.mp3")

def test_path_traversal_filename(env, tmp_path):
    s, st, fs, v, up = env; sg = song(st)
    up.upload(sg.id, chunks(b"x"), "../../evil.mp3")
    assert st.get_song(sg.id).original_name == "evil.mp3"
    assert not (tmp_path.parent / "evil.mp3").exists() and fs.list_files(sg.id) == ["original.mp3"]
    assert safe_display_name("C:\\x\\y\\a\x00.mp3") == "a.mp3"

@pytest.mark.parametrize("bad", ["../x", "..", "abc", "", "/etc/passwd"])
def test_song_dir_rejects_bad_ids(env, bad):
    with pytest.raises(ValueError): env[2].song_dir(bad)

def _done(st, sid):
    st.db.execute("UPDATE songs SET status='CONCLUIDA' WHERE id=?", (sid,))

def test_reconcile_never_deletes(env):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3"); _done(st, sg.id)
    orphan = fs.songs / "11111111-1111-4111-8111-111111111111"; orphan.mkdir()
    r = ReconcileService(st, fs).run()
    assert r["songs"][0]["issues"] == ["stems_ausentes"] and not r["songs"][0]["pronta"]
    assert r["orphan_dirs"] == [orphan.name] and orphan.exists()
    d = fs.song_dir(sg.id)
    (d / "instrumental.wav").write_bytes(b"i"); (d / "vocals.wav").write_bytes(b"v")
    assert ReconcileService(st, fs).run()["songs"][0]["pronta"]

def test_reconcile_missing_folder(env):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3")
    import shutil; shutil.rmtree(fs.song_dir(sg.id))
    assert ReconcileService(st, fs).run()["songs"][0]["issues"] == ["pasta_ausente"]

def test_delete_removes_files_and_rows(env):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3")
    r = DeletionService(st, fs).delete(sg.id)
    assert r == {"deleted": True, "files_removed": True}
    assert not fs.song_dir(sg.id).exists() and st.list_songs() == [] and st.list_jobs() == []

def test_delete_blocked_when_processing(env):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3"); st.claim_next()
    with pytest.raises(Conflict): DeletionService(st, fs).delete(sg.id)
    assert fs.list_files(sg.id) == ["original.mp3"]

def test_delete_rolls_back_files_if_db_fails(env, monkeypatch):
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3")
    def boom(_): raise RuntimeError("db")
    monkeypatch.setattr(st, "delete_song", boom)
    with pytest.raises(RuntimeError): DeletionService(st, fs).delete(sg.id)
    assert fs.list_files(sg.id) == ["original.mp3"] and len(st.list_songs()) == 1

def test_delete_partial_failure_reported_and_purged(env, monkeypatch):
    import shutil
    s, st, fs, v, up = env; sg = song(st); up.upload(sg.id, chunks(b"x"), "a.mp3")
    real = shutil.rmtree
    def fail(*a, **k): raise OSError("locked")
    monkeypatch.setattr(shutil, "rmtree", fail)
    r = DeletionService(st, fs).delete(sg.id)
    assert r["files_removed"] is False and st.list_songs() == []
    monkeypatch.setattr(shutil, "rmtree", real)
    assert fs.purge_trash() == 1

def test_delete_without_folder(env):
    s, st, fs, v, up = env; sg = song(st)
    assert DeletionService(st, fs).delete(sg.id)["deleted"]
