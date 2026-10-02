"""Imagem de fundo própria de cada música (guardada no SQLite, validada por conteúdo)."""
import base64

MAX_BYTES = 256_000


class InvalidBackground(ValueError):
    pass


def image_to_data_url(raw: bytes) -> str:
    if len(raw) < 12 or len(raw) > MAX_BYTES:
        raise InvalidBackground("imagem deve ter até 256 KB")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise InvalidBackground("conteúdo da imagem inválido: use PNG, JPEG ou WebP")
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


class SongBackgrounds:
    """Uma imagem por música; ao excluir a música, a imagem é removida em cascata."""

    def __init__(self, store):
        self.store = store
        with self.store._tx() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS song_backgrounds("
                "song_id TEXT PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE, "
                "data_url TEXT NOT NULL)"
            )

    def get(self, song_id: str) -> str:
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT data_url FROM song_backgrounds WHERE song_id=?", (song_id,)
            ).fetchone()
        return row["data_url"] if row else ""

    def has(self, song_id: str) -> bool:
        return bool(self.get(song_id))

    def ids(self) -> list[str]:
        with self.store.lock:
            rows = self.store.db.execute("SELECT song_id FROM song_backgrounds ORDER BY song_id").fetchall()
        return [r["song_id"] for r in rows]

    def set(self, song_id: str, raw: bytes) -> None:
        self.store.get_song(song_id)  # NotFound se a música não existir
        data_url = image_to_data_url(raw)
        with self.store._tx() as c:
            c.execute(
                "INSERT INTO song_backgrounds(song_id,data_url) VALUES(?,?) "
                "ON CONFLICT(song_id) DO UPDATE SET data_url=excluded.data_url",
                (song_id, data_url),
            )

    def clear(self, song_id: str) -> None:
        self.store.get_song(song_id)
        with self.store._tx() as c:
            c.execute("DELETE FROM song_backgrounds WHERE song_id=?", (song_id,))
