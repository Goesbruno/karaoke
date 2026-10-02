"""Configuração do separador resolvida a partir da raiz do projeto, nunca do diretório atual."""
import os
from dataclasses import dataclass
from pathlib import Path
from .infrastructure.model_manifest import MODEL_FILENAME, MODEL_SHA256

ROOT = Path(__file__).resolve().parents[3]
BVE_FILE = "UVR-BVE-4B_SN-44100-1.pth"
BVE_SHA256 = "56165bdfa0dd5df7930ff76652200dc287e1bfef622bba5c812c736dc22067fe"


def _local(value: str, description: str) -> Path:
    path = Path(value).expanduser()
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"{description} deve ficar dentro da raiz do projeto: {resolved}")
    return resolved


def _file_name(value: str, description: str) -> str:
    if not value or Path(value).name != value or value in (".", "..") or "\\" in value or "/" in value:
        raise ValueError(f"{description} deve ser somente o nome do arquivo")
    return value


@dataclass
class SeparatorSettings:
    cmd: str
    model_dir: Path
    model_file: str
    model_sha256: str
    bve_model_file: str
    bve_model_sha256: str
    overlap: int = 2
    segment_size: int | None = None
    batch_size: int = 1
    autocast: bool = False
    timeout_s: int = 3600
    cpu_fallback: bool = True
    reduced_segments: tuple[int, ...] = (128, 64)
    ffmpeg_path: str = "ffmpeg"
    tolerance_s: float = 0.1

    @classmethod
    def from_env(cls, env=None) -> "SeparatorSettings":
        e = os.environ if env is None else env
        exe = ".venv-separator/Scripts/audio-separator.exe" if os.name == "nt" else ".venv-separator/bin/audio-separator"
        seg = e.get("KARAOKE_SEP_SEGMENT_SIZE", "")
        return cls(
            cmd=str(_local(e.get("KARAOKE_SEPARATOR_CMD") or exe, "KARAOKE_SEPARATOR_CMD")),
            model_dir=_local(e.get("KARAOKE_MODEL_DIR") or "models", "KARAOKE_MODEL_DIR"),
            model_file=_file_name(e.get("KARAOKE_MODEL_FILE") or MODEL_FILENAME, "KARAOKE_MODEL_FILE"),
            model_sha256=(e.get("KARAOKE_MODEL_SHA256") or MODEL_SHA256).lower(),
            bve_model_file=_file_name(e.get("KARAOKE_BVE_MODEL_FILE") or BVE_FILE, "KARAOKE_BVE_MODEL_FILE"),
            bve_model_sha256=(e.get("KARAOKE_BVE_MODEL_SHA256") or BVE_SHA256).lower(),
            overlap=int(e.get("KARAOKE_SEP_OVERLAP", "2")),
            segment_size=int(seg) if seg else None,
            batch_size=int(e.get("KARAOKE_SEP_BATCH_SIZE", "1")),
            autocast=e.get("KARAOKE_SEP_AUTOCAST", "0") == "1",
            timeout_s=int(e.get("KARAOKE_SEP_TIMEOUT_S", "3600")),
            cpu_fallback=e.get("KARAOKE_SEP_CPU_FALLBACK", "1") == "1",
            ffmpeg_path=e.get("KARAOKE_FFMPEG_PATH", "ffmpeg"),
            tolerance_s=float(e.get("KARAOKE_SEP_TOLERANCE_S", "0.1")),
        )
