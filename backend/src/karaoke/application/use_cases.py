from .ports import JobQueue, SongStore
from ..domain.entities import Job, Song

class LibraryService:
    def __init__(self, songs: SongStore, queue: JobQueue, max_attempts: int = 3):
        self.songs, self.queue, self.max_attempts = songs, queue, max_attempts

    def add_song(self, title: str, artist: str = "", source_video_id: str | None = None) -> Song:
        title = title.strip()
        if not title:
            raise ValueError("titulo obrigatorio")
        return self.songs.create_song(title, artist.strip(), source_video_id)

    def enqueue_uploaded(self, song_id: str) -> Job:
        """Chamado apos upload validado (modulo 2). Aqui apenas move para a fila."""
        self.songs.get_song(song_id)
        return self.queue.enqueue(song_id, self.max_attempts)
