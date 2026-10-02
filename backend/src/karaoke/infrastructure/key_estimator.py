import numpy as np
from ..application.separation import KeyResult
from .wav_tools import read_pcm16

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def _label(k: int, minor: bool) -> str: return f"{NAMES[k]} {'menor' if minor else 'maior'}"

class NumpyKeyEstimator:
    """Krumhansl-Schmuckler sobre cromagrama. Limiares sao heuristicas iniciais, a calibrar com musicas reais."""
    def __init__(self, max_seconds=120, min_score=0.55, min_margin=0.03, n_fft=8192, fmin=110.0, fmax=2100.0, flat_ratio=0.05):
        self.max_seconds, self.min_score, self.min_margin = max_seconds, min_score, min_margin
        self.n_fft, self.fmin, self.fmax, self.flat_ratio = n_fft, fmin, fmax, flat_ratio

    def _chroma(self, x, sr):
        hop = self.n_fft // 2
        n = 1 + (len(x) - self.n_fft) // hop
        idx = np.arange(self.n_fft)[None, :] + hop * np.arange(n)[:, None]
        mag = np.abs(np.fft.rfft(x[idx] * np.hanning(self.n_fft), axis=1))
        freqs = np.fft.rfftfreq(self.n_fft, 1 / sr)
        mask = (freqs >= self.fmin) & (freqs <= self.fmax)
        pc = np.round(12 * np.log2(freqs[mask] / 440.0) + 69).astype(int) % 12
        return np.bincount(pc, weights=np.sqrt(mag).sum(axis=0)[mask], minlength=12)

    def estimate(self, wav) -> KeyResult:
        data, sr, _ = read_pcm16(wav)
        if data.size == 0: return KeyResult(None, warning="audio vazio")
        x = data.astype(np.float64).mean(axis=1) / 32768.0
        if len(x) < sr * 5: return KeyResult(None, warning="audio curto demais para estimar o tom")
        if len(x) > sr * self.max_seconds:
            s = (len(x) - sr * self.max_seconds) // 2
            x = x[s:s + sr * self.max_seconds]
        if np.abs(x).max() < 1e-4: return KeyResult(None, warning="audio silencioso; tom inconclusivo")
        ch = self._chroma(x, sr)
        if ch.std() / (ch.mean() + 1e-12) < self.flat_ratio:
            return KeyResult(None, warning="sem tonalidade definida (cromagrama plano); tom inconclusivo")
        scores = []
        for minor, prof in ((False, MAJOR), (True, MINOR)):
            for k in range(12):
                scores.append((float(np.corrcoef(ch, np.roll(prof, k))[0, 1]), k, minor))
        scores.sort(reverse=True)
        (b, k, minor), (s2, k2, m2) = scores[0], scores[1]
        margin = b - s2
        conf = float(np.clip(margin / 0.15, 0, 1))
        if b < self.min_score or margin < self.min_margin:
            return KeyResult(None, b, conf, f"tom inconclusivo (correlacao {b:.2f}, margem {margin:.2f}); corrija manualmente")
        rel = (k + 9) % 12 if not minor else (k + 3) % 12
        warn = ""
        if k2 == rel and m2 != minor:
            warn = f"ambiguidade com o tom relativo ({_label(k2, m2)}); confirme de ouvido"
        return KeyResult(_label(k, minor), b, conf, warn)
