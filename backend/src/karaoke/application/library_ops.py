import re
from pathlib import Path
from ..domain.errors import Conflict, Duplicate, UploadRejected
from ..domain.states import State

ESSENTIAL_STEMS = ("instrumental.wav", "vocals.wav")  # nomes finais definidos no modulo do separador

def safe_display_name(name: str) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:120]
    return name or "arquivo"

def ext_of(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")

CHUNK = 1024 * 1024

class UploadService:
    def __init__(self, store, files, validator, settings):
        self.store, self.files, self.validator, self.s = store, files, validator, settings

    def upload(self, song_id, chunks, filename, allow_homonym=False):
        song = self.store.get_song(song_id)
        if song.status != State.AGUARDANDO_UPLOAD:
            raise Conflict(f"musica em estado {song.status.value}; upload nao permitido")
        display = safe_display_name(filename)
        ext = ext_of(display)
        if ext not in self.s.allowed_ext:
            raise UploadRejected("extensao", f"extensao .{ext or '?'} nao permitida ({', '.join(self.s.allowed_ext)})")
        if self.files.free_bytes() < self.s.min_free_mb * 1024 * 1024 + self.s.max_upload_bytes:
            raise UploadRejected("espaco", "espaco em disco insuficiente")
        try:
            tmp, sha, _ = self.files.save_stream(song_id, chunks, self.s.max_upload_bytes)
            info = self.validator.probe(tmp, ext)
            if not (self.s.min_duration_s <= info.duration_s <= self.s.max_duration_s):
                raise UploadRejected("duracao", f"duracao {info.duration_s:.0f}s fora do intervalo permitido")
            other = self.store.find_by_sha(sha)
            if other:
                raise Duplicate("duplicado", "arquivo identico ja existe na biblioteca", other.id)
            if not allow_homonym:
                h = self.store.find_homonyms(song.title, song.artist, song_id)
                if h:
                    raise Duplicate("homonimo", "ja existe musica com mesmo titulo e artista e conteudo diferente", h[0].id)
            final = self.files.commit(song_id, tmp, ext)
            try:
                self.store.set_file(song_id, sha, info.duration_s, display, ext)
            except BaseException:
                final.unlink(missing_ok=True); raise
        except BaseException:
            self.files.discard_tmp(song_id); raise
        return self.store.enqueue(song_id, self.s.max_attempts)

class ReconcileService:
    """Apenas diagnostica. Nunca apaga dados."""
    def __init__(self, store, files, essential=ESSENTIAL_STEMS):
        self.store, self.files, self.essential = store, files, essential

    def run(self):
        songs, report = self.store.list_songs(), []
        dirs = set(self.files.list_song_dirs())
        for s in songs:
            present = self.files.list_files(s.id) if s.id in dirs else []
            issues = []
            if s.id not in dirs and s.status != State.AGUARDANDO_UPLOAD:
                issues.append("pasta_ausente")
            elif s.status not in (State.AGUARDANDO_UPLOAD, State.CANCELADA) and not any(f.startswith("original.") for f in present):
                issues.append("original_ausente")
            if s.status == State.CONCLUIDA and any(e not in present for e in self.essential):
                issues.append("stems_ausentes")
            report.append({"id": s.id, "title": s.title, "status": s.status.value, "issues": issues,
                           "pronta": s.status == State.CONCLUIDA and not issues})
        known = {s.id for s in songs}
        return {"songs": report, "orphan_dirs": sorted(dirs - known)}

class DeletionService:
    def __init__(self, store, files):
        self.store, self.files = store, files

    def delete(self, song_id):
        self.store.get_song(song_id)
        token = self.files.begin_delete(song_id)
        try:
            self.store.delete_song(song_id)
        except BaseException:
            self.files.rollback_delete(token); raise
        return {"deleted": True, "files_removed": self.files.finish_delete(token)}
