import wave
from pathlib import Path
import numpy as np
from ..application.separation import SeparationError, WavInfo

def read_pcm16(path) -> tuple[np.ndarray, int, int]:
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2: raise SeparationError("WAV nao suportado: esperado PCM de 16 bits")
            ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
            data = np.frombuffer(w.readframes(n), dtype=np.int16)
    except (wave.Error, EOFError) as e:
        raise SeparationError(f"WAV invalido: {e}")
    return data.reshape(-1, ch) if ch > 0 else data, sr, ch

class WavInspector:
    def inspect(self, path: Path) -> WavInfo:
        data, sr, ch = read_pcm16(path)
        if data.size == 0: return WavInfo(sr, ch, 0)
        a = np.abs(data.astype(np.int32))
        return WavInfo(sr, ch, data.shape[0], int(a.max()), float((a >= 32767).mean()))
