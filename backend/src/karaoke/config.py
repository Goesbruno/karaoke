import json, os, secrets
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROLES = {
    "host": ["songs:create", "songs:upload", "songs:enqueue", "songs:delete", "jobs:retry", "jobs:cancel",
             "jobs:read", "songs:read", "library:diagnostics", "network:read", "search:read", "lyrics:search", "lyrics:read", "lyrics:choose", "songs:edit", "session:control", "session:manage"],
    "guest": ["songs:create", "jobs:read", "songs:read", "search:read", "lyrics:search", "lyrics:read", "session:control"],
}

@dataclass
class Settings:
    data_dir: Path = Path("./data")
    host: str = "0.0.0.0"
    port: int = 8000
    advertise_ip: str = ""
    max_gpu_jobs: int = 1
    max_attempts: int = 3
    host_token: str = ""
    guest_token: str = ""
    roles: dict = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_ROLES.items()})
    allowed_ext: tuple = ("mp3", "wav", "flac", "m4a", "ogg")
    max_upload_mb: int = 200
    min_duration_s: float = 30
    max_duration_s: float = 1200
    min_free_mb: int = 2048
    ffprobe_path: str = "ffprobe"
    lrclib_client_id: str = "KaraokeLAN/0.6 (admin@example.org)"
    youtube_api_key: str = ""
    frontend_dist: Path = Path("frontend/dist")
    youtube_download_dir: str = ""
    youtube_mp3_quality: str = "192"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "karaoke.db"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        e = os.environ if env is None else env
        return cls(
            data_dir=Path(e.get("KARAOKE_DATA_DIR", "./data")),
            host=e.get("KARAOKE_HOST", "0.0.0.0"),
            port=int(e.get("KARAOKE_PORT", "8000")),
            advertise_ip=e.get("KARAOKE_ADVERTISE_IP", ""),
            max_gpu_jobs=int(e.get("KARAOKE_MAX_GPU_JOBS", "1")),
            max_attempts=int(e.get("KARAOKE_MAX_ATTEMPTS", "3")),
            host_token=e.get("KARAOKE_HOST_TOKEN") or secrets.token_urlsafe(24),
            guest_token=e.get("KARAOKE_GUEST_TOKEN") or secrets.token_urlsafe(24),
            roles=json.loads(e["KARAOKE_ROLES"]) if e.get("KARAOKE_ROLES") else {k: list(v) for k, v in DEFAULT_ROLES.items()},
            allowed_ext=tuple(x.strip().lower().lstrip(".") for x in e.get("KARAOKE_ALLOWED_EXT", "mp3,wav,flac,m4a,ogg").split(",") if x.strip()),
            max_upload_mb=int(e.get("KARAOKE_MAX_UPLOAD_MB", "200")),
            min_duration_s=float(e.get("KARAOKE_MIN_DURATION_S", "30")),
            max_duration_s=float(e.get("KARAOKE_MAX_DURATION_S", "1200")),
            min_free_mb=int(e.get("KARAOKE_MIN_FREE_MB", "2048")),
            ffprobe_path=e.get("KARAOKE_FFPROBE_PATH", "ffprobe"),
            lrclib_client_id=e.get("KARAOKE_LRCLIB_CLIENT_ID", "KaraokeLAN/0.6 (admin@example.org)"),
            youtube_api_key=e.get("YOUTUBE_API_KEY", ""),
            frontend_dist=Path(e.get("KARAOKE_FRONTEND_DIST", "frontend/dist")),
            youtube_download_dir=os.environ.get(
                "KARAOKE_YOUTUBE_DOWNLOAD_DIR",
                "",  # vazio = usa tempfile.gettempdir()
            ),
            youtube_mp3_quality=os.environ.get("KARAOKE_YOUTUBE_MP3_QUALITY", "192"),
        )
