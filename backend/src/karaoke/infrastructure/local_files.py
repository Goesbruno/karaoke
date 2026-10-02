import hashlib, os, shutil, uuid
from pathlib import Path
from ..domain.errors import UploadRejected

TMP_NAME = ".upload.tmp"

class LocalFileStore:
    """Sistema de arquivos: <data>/songs/<uuid>/. Todo caminho e derivado de UUID validado."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.songs = self.root / "songs"
        self.trash = self.root / ".trash"
        self.songs.mkdir(parents=True, exist_ok=True)
        self.trash.mkdir(parents=True, exist_ok=True)

    def free_bytes(self) -> int:
        return shutil.disk_usage(self.root).free

    def song_dir(self, song_id: str) -> Path:
        try:
            canon = str(uuid.UUID(str(song_id)))
        except ValueError:
            raise ValueError("id de musica invalido")
        if canon != str(song_id).lower():
            raise ValueError("id de musica invalido")
        p = (self.songs / canon).resolve()
        if p.parent != self.songs.resolve():
            raise ValueError("caminho fora da pasta de musicas")
        return p

    def save_stream(self, song_id, chunks, max_bytes):
        d = self.song_dir(song_id); d.mkdir(exist_ok=True)
        tmp = d / TMP_NAME
        h, size = hashlib.sha256(), 0
        try:
            with open(tmp, "wb") as f:
                for ch in chunks:
                    size += len(ch)
                    if size > max_bytes:
                        raise UploadRejected("tamanho", "arquivo excede o limite de upload")
                    h.update(ch); f.write(ch)
                f.flush(); os.fsync(f.fileno())
        except BaseException:
            self.discard_tmp(song_id); raise
        if size == 0:
            self.discard_tmp(song_id)
            raise UploadRejected("vazio", "arquivo vazio")
        return tmp, h.hexdigest(), size

    def commit(self, song_id, tmp, ext):
        final = self.song_dir(song_id) / f"original.{ext}"
        os.replace(tmp, final)
        return final

    def discard_tmp(self, song_id):
        d = self.song_dir(song_id)
        try: (d / TMP_NAME).unlink()
        except FileNotFoundError: pass
        try: d.rmdir()  # so remove se ficou vazia
        except OSError: pass

    def list_files(self, song_id):
        d = self.song_dir(song_id)
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def list_song_dirs(self):
        out = []
        for p in self.songs.iterdir():
            if p.is_dir():
                try: uuid.UUID(p.name); out.append(p.name)
                except ValueError: pass
        return sorted(out)

    def begin_delete(self, song_id):
        d = self.song_dir(song_id)
        if not d.exists(): return None
        dest = self.trash / f"{d.name}.{uuid.uuid4().hex}"
        os.replace(d, dest)
        return (d, dest)

    def rollback_delete(self, token):
        if token: os.replace(token[1], token[0])

    def finish_delete(self, token) -> bool:
        if token is None: return True
        try:
            shutil.rmtree(token[1]); return True
        except OSError:
            return False

    def purge_trash(self):
        n = 0
        for p in self.trash.iterdir():
            try: shutil.rmtree(p); n += 1
            except OSError: pass
        return n
