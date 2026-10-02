from dataclasses import dataclass
from .states import State, TRANSITIONS
from .errors import InvalidTransition

def ensure_transition(cur: State, new: State) -> None:
    if new not in TRANSITIONS[cur]:
        raise InvalidTransition(f"{cur.value} -> {new.value} nao permitido")

@dataclass
class Song:
    id: str
    title: str
    artist: str
    status: State
    source_video_id: str | None = None
    created_at: str = ""
    sha256: str | None = None
    duration_s: float | None = None
    original_name: str = ""
    ext: str = ""

@dataclass
class Job:
    id: int
    song_id: str
    state: State
    step: str = ""
    message: str = ""
    attempts: int = 0
    max_attempts: int = 3
    error: str = ""
