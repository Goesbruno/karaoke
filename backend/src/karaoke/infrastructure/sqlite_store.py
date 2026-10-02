import sqlite3, uuid, threading
from datetime import datetime, timezone
from pathlib import Path
from ..domain.entities import Job, Song, ensure_transition
from ..domain.errors import Conflict, Duplicate, NotFound, RetryLimit
from ..domain.states import ACTIVE, State

V1 = """
CREATE TABLE IF NOT EXISTS songs(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL, source_video_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, song_id TEXT NOT NULL REFERENCES songs(id),
  state TEXT NOT NULL, step TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
  error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state, id);
"""
V2 = """
BEGIN;
ALTER TABLE songs ADD COLUMN sha256 TEXT;
ALTER TABLE songs ADD COLUMN duration_s REAL;
ALTER TABLE songs ADD COLUMN original_name TEXT NOT NULL DEFAULT '';
ALTER TABLE songs ADD COLUMN ext TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_sha ON songs(sha256) WHERE sha256 IS NOT NULL;
COMMIT;
"""
V3 = """
BEGIN;
ALTER TABLE songs ADD COLUMN key_manual TEXT;
COMMIT;
"""
V4 = """
BEGIN;
ALTER TABLE songs ADD COLUMN lyrics_offset_ms INTEGER NOT NULL DEFAULT 0;
COMMIT;
"""
MIGRATIONS = [V1, V2, V3, V4]

def _now(): return datetime.now(timezone.utc).isoformat()

class SqliteStore:
    """Implementa SongStore e JobQueue. Migracoes versionadas via PRAGMA user_version."""
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self):
        v = self.db.execute("PRAGMA user_version").fetchone()[0]
        for i, sql in enumerate(MIGRATIONS, 1):
            if i > v:
                self.db.executescript(sql)
                self.db.execute(f"PRAGMA user_version={i}")

    def _tx(self): return _Tx(self)

    @staticmethod
    def _song(r):
        return Song(r["id"], r["title"], r["artist"], State(r["status"]), r["source_video_id"], r["created_at"],
                    sha256=r["sha256"], duration_s=r["duration_s"], original_name=r["original_name"], ext=r["ext"])
    @staticmethod
    def _job(r): return Job(r["id"], r["song_id"], State(r["state"]), r["step"], r["message"], r["attempts"], r["max_attempts"], r["error"])

    def create_song(self, title, artist, source_video_id):
        s = Song(str(uuid.uuid4()), title, artist, State.AGUARDANDO_UPLOAD, source_video_id, _now())
        with self._tx() as c:
            c.execute("INSERT INTO songs(id,title,artist,status,source_video_id,created_at) VALUES(?,?,?,?,?,?)",
                      (s.id, s.title, s.artist, s.status.value, s.source_video_id, s.created_at))
        return s

    def get_song(self, song_id):
        with self.lock:
            r = self.db.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
        if not r: raise NotFound(song_id)
        return self._song(r)

    def list_songs(self):
        with self.lock:
            return [self._song(r) for r in self.db.execute("SELECT * FROM songs ORDER BY created_at")]

    def update_metadata(self, song_id, title, artist, key_manual):
        with self._tx() as c:
            r = c.execute("SELECT id FROM songs WHERE id=?", (song_id,)).fetchone()
            if r is None: raise NotFound(song_id)
            c.execute("UPDATE songs SET title=?, artist=?, key_manual=? WHERE id=?",
                      (title, artist, key_manual, song_id))
        return self.get_song(song_id)

    def manual_key(self, song_id):
        with self.lock:
            r = self.db.execute("SELECT key_manual FROM songs WHERE id=?", (song_id,)).fetchone()
        if r is None: raise NotFound(song_id)
        return r["key_manual"]

    def lyrics_offset(self, song_id):
        with self.lock:
            r=self.db.execute("SELECT lyrics_offset_ms FROM songs WHERE id=?",(song_id,)).fetchone()
        if r is None: raise NotFound(song_id)
        return r["lyrics_offset_ms"]

    def set_lyrics_offset(self, song_id, ms):
        if not isinstance(ms,int) or not -10000 <= ms <= 10000:
            raise ValueError("offset deve estar entre -10000 e +10000 ms")
        with self._tx() as c:
            r=c.execute("UPDATE songs SET lyrics_offset_ms=? WHERE id=?",(ms,song_id))
            if not r.rowcount: raise NotFound(song_id)
        return ms

    def find_by_sha(self, sha):
        with self.lock:
            r = self.db.execute("SELECT * FROM songs WHERE sha256=?", (sha,)).fetchone()
        return self._song(r) if r else None

    def find_homonyms(self, title, artist, exclude_id):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM songs WHERE lower(title)=lower(?) AND lower(artist)=lower(?) AND id<>? AND sha256 IS NOT NULL",
                (title, artist, exclude_id)).fetchall()
        return [self._song(r) for r in rows]

    def set_file(self, song_id, sha256, duration_s, original_name, ext):
        try:
            with self._tx() as c:
                cur = c.execute("UPDATE songs SET sha256=?, duration_s=?, original_name=?, ext=? WHERE id=?",
                                (sha256, duration_s, original_name, ext, song_id))
                if cur.rowcount == 0: raise NotFound(song_id)
        except sqlite3.IntegrityError:
            other = self.find_by_sha(sha256)
            raise Duplicate("duplicado", "arquivo identico ja existe na biblioteca", other.id if other else None)

    def delete_song(self, song_id):
        with self._tx() as c:
            if not c.execute("SELECT 1 FROM songs WHERE id=?", (song_id,)).fetchone(): raise NotFound(song_id)
            act = c.execute(f"SELECT 1 FROM jobs WHERE song_id=? AND state IN ({','.join('?'*len(ACTIVE))})",
                            [song_id, *[s.value for s in ACTIVE]]).fetchone()
            if act: raise Conflict("musica em processamento; cancele o trabalho antes de excluir")
            c.execute("DELETE FROM jobs WHERE song_id=?", (song_id,))
            c.execute("DELETE FROM songs WHERE id=?", (song_id,))

    def get_job(self, job_id):
        with self.lock:
            r = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r: raise NotFound(str(job_id))
        return self._job(r)

    def list_jobs(self):
        with self.lock:
            return [self._job(r) for r in self.db.execute("SELECT * FROM jobs ORDER BY id")]

    def _set(self, c, job_id, state, step=None, message=None, error=None, attempts_inc=0):
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r: raise NotFound(str(job_id))
        ensure_transition(State(r["state"]), state)
        c.execute("UPDATE jobs SET state=?, step=?, message=?, error=?, attempts=attempts+?, updated_at=? WHERE id=?",
                  (state.value, r["step"] if step is None else step, r["message"] if message is None else message,
                   r["error"] if error is None else error, attempts_inc, _now(), job_id))
        c.execute("UPDATE songs SET status=? WHERE id=?", (state.value, r["song_id"]))
        return self._job(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def enqueue(self, song_id, max_attempts):
        with self._tx() as c:
            r = c.execute("SELECT status FROM songs WHERE id=?", (song_id,)).fetchone()
            if not r: raise NotFound(song_id)
            ensure_transition(State(r["status"]), State.NA_FILA)
            cur = c.execute("INSERT INTO jobs(song_id,state,max_attempts,updated_at) VALUES(?,?,?,?)",
                            (song_id, State.NA_FILA.value, max_attempts, _now()))
            c.execute("UPDATE songs SET status=? WHERE id=?", (State.NA_FILA.value, song_id))
            return self._job(c.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())

    def claim_next(self):
        with self._tx() as c:
            r = c.execute("SELECT id FROM jobs WHERE state=? ORDER BY id LIMIT 1", (State.NA_FILA.value,)).fetchone()
            if not r: return None
            return self._set(c, r["id"], State.PREPARANDO, step="preparando", message="", attempts_inc=1)

    def advance(self, job_id, state, step="", message=""):
        with self._tx() as c:
            return self._set(c, job_id, state, step=step or state.value.lower(), message=message)

    def fail(self, job_id, error):
        with self._tx() as c:
            return self._set(c, job_id, State.FALHA, error=error)

    def cancel(self, job_id):
        with self._tx() as c:
            return self._set(c, job_id, State.CANCELADA)

    def retry(self, job_id):
        with self._tx() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not r: raise NotFound(str(job_id))
            if r["attempts"] >= r["max_attempts"]: raise RetryLimit("limite de tentativas atingido")
            return self._set(c, job_id, State.NA_FILA, error="", message="nova tentativa")

    def recover(self):
        out = []
        with self._tx() as c:
            rows = c.execute(f"SELECT * FROM jobs WHERE state IN ({','.join('?'*len(ACTIVE))})", [s.value for s in ACTIVE]).fetchall()
            for r in rows:
                msg = "interrompido por reinicio"
                if r["attempts"] >= r["max_attempts"]:
                    out.append(self._set(c, r["id"], State.FALHA, error=msg))
                else:
                    c.execute("UPDATE jobs SET state=?, message=?, updated_at=? WHERE id=?", (State.NA_FILA.value, msg, _now(), r["id"]))
                    c.execute("UPDATE songs SET status=? WHERE id=?", (State.NA_FILA.value, r["song_id"]))
                    out.append(self._job(c.execute("SELECT * FROM jobs WHERE id=?", (r["id"],)).fetchone()))
        return out

    def position(self, job_id):
        j = self.get_job(job_id)
        if j.state != State.NA_FILA: return None
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM jobs WHERE state=? AND id<=?", (State.NA_FILA.value, job_id)).fetchone()[0]

class _Tx:
    def __init__(self, s): self.s = s
    def __enter__(self):
        self.s.lock.acquire()
        self.s.db.execute("BEGIN IMMEDIATE")
        return self.s.db
    def __exit__(self, et, ev, tb):
        try:
            self.s.db.execute("ROLLBACK" if et else "COMMIT")
        finally:
            self.s.lock.release()
