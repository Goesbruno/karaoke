import subprocess
from pathlib import Path
from ..application.separation import SeparationError

class FfmpegPreparer:
    """Converte o original autorizado para WAV PCM 16 bits, 44,1 kHz, estereo."""
    def __init__(self, ffmpeg_path="ffmpeg", runner=subprocess.run, timeout=600):
        self.path, self.runner, self.timeout = ffmpeg_path, runner, timeout

    def to_wav(self, src: Path, dst: Path) -> None:
        cmd = [self.path, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(dst)]
        try:
            r = self.runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout)
        except FileNotFoundError:
            raise SeparationError("ffmpeg nao encontrado; ajuste KARAOKE_FFMPEG_PATH")
        except subprocess.TimeoutExpired:
            raise SeparationError("tempo esgotado na conversao com ffmpeg")
        if r.returncode != 0 or not Path(dst).is_file():
            raise SeparationError(f"falha na conversao com ffmpeg: {(r.stderr or '').strip()[-300:]}")
