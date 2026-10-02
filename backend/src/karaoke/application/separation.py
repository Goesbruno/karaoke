import json, os, shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol
from ..domain.states import State

class SeparationError(Exception): pass
class OutOfMemory(SeparationError): pass

@dataclass
class WavInfo:
    sample_rate: int
    channels: int
    frames: int
    peak: int = 0
    clip_ratio: float = 0.0
    @property
    def duration(self) -> float: return self.frames / self.sample_rate if self.sample_rate else 0.0

@dataclass
class SeparationResult:
    instrumental: Path
    vocals: Path
    meta: dict = field(default_factory=dict)

@dataclass
class KeyResult:
    key: str | None
    score: float = 0.0
    confidence: float = 0.0
    warning: str = ""

class AudioPreparer(Protocol):
    def to_wav(self, src: Path, dst: Path) -> None: ...
class AudioSeparator(Protocol):
    def separate(self, wav: Path, out_dir: Path) -> SeparationResult: ...
class LeadBackingSplitter(Protocol):
    def split(self, vocals: Path, out_dir: Path) -> tuple[Path, Path, dict]: ...
class KeyEstimator(Protocol):
    def estimate(self, wav: Path) -> KeyResult: ...
class WavInspector(Protocol):
    def inspect(self, path: Path) -> WavInfo: ...

def check_stem(name: str, info: WavInfo, ref: WavInfo, tol_s: float) -> list[str]:
    if info.frames == 0: raise SeparationError(f"{name}: arquivo sem amostras")
    if info.sample_rate != ref.sample_rate:
        raise SeparationError(f"{name}: taxa de amostragem {info.sample_rate} difere da entrada ({ref.sample_rate})")
    if info.channels != ref.channels:
        raise SeparationError(f"{name}: {info.channels} canais; a entrada tem {ref.channels}")
    if abs(info.duration - ref.duration) > tol_s:
        raise SeparationError(f"{name}: duracao {info.duration:.3f}s difere da entrada ({ref.duration:.3f}s)")
    warnings = []
    if info.peak == 0:
        if name == "instrumental":
            raise SeparationError("instrumental silencioso (possivel falha na separacao)")
        warnings.append(f"{name} silencioso (a faixa pode nao ter esse conteudo)")
    if info.clip_ratio > 0.01:
        warnings.append(f"{name}: {info.clip_ratio:.1%} das amostras saturadas")
    return warnings

LEAD_BACKING_OFF = "Nenhum modelo lead/backing validado; instrumental e vocais estao disponiveis."

class ProcessingPipeline:
    """Executa as etapas de um trabalho. Nada e publicado antes de todas as validacoes passarem."""
    def __init__(self, song_dir_of: Callable[[str], Path], preparer, separator, key_estimator, inspector,
                 lead_backing=None, model_info: dict | None = None, tolerance_s: float = 0.1):
        self.song_dir_of, self.preparer, self.separator = song_dir_of, preparer, separator
        self.key_estimator, self.inspector, self.lead_backing = key_estimator, inspector, lead_backing
        self.model_info, self.tol = model_info or {}, tolerance_s

    def run(self, job, advance) -> None:
        d = Path(self.song_dir_of(job.song_id))
        originals = sorted(d.glob("original.*"))
        if not originals: raise SeparationError("arquivo original ausente na pasta da musica")
        work = d / ".work"
        shutil.rmtree(work, ignore_errors=True); work.mkdir()
        published: list[Path] = []
        try:
            prepared = work / "input.wav"
            self.preparer.to_wav(originals[0], prepared)
            ref = self.inspector.inspect(prepared)
            advance(State.SEPARANDO_INSTRUMENTAL_VOCAIS, "separando instrumental e vocais")
            res = self.separator.separate(prepared, work / "stems")
            warnings: list[str] = []
            outputs = {"instrumental.wav": res.instrumental, "vocals.wav": res.vocals}
            for name, p in (("instrumental", res.instrumental), ("vocals", res.vocals)):
                warnings += check_stem(name, self.inspector.inspect(p), ref, self.tol)
            lb: dict = {"available": False, "reason": LEAD_BACKING_OFF}
            if self.lead_backing is not None:
                advance(State.SEPARANDO_LEAD_BACKING, "separando vocal principal e backing")
                lead, backing, lbmeta = self.lead_backing.split(res.vocals, work / "lead_backing")
                for name, p in (("lead", lead), ("backing", backing)):
                    warnings += check_stem(name, self.inspector.inspect(p), ref, self.tol)
                outputs.update({"lead.wav": lead, "backing.wav": backing})
                lb = {"available": True, **lbmeta}
            advance(State.ANALISANDO, "estimando o tom")
            try:
                key = self.key_estimator.estimate(prepared)
            except Exception as e:
                key = KeyResult(None, warning=f"analise de tom falhou: {e}"); warnings.append(key.warning)
            for fname, src in outputs.items():
                dst = d / fname
                os.replace(src, dst); published.append(dst)
            meta = {
                "schema": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "model": self.model_info, "separation": res.meta,
                "input": {"sample_rate": ref.sample_rate, "channels": ref.channels, "duration_s": round(ref.duration, 3)},
                "stems": sorted(outputs), "lead_backing": lb,
                "key": {"estimated": key.key, "score": round(key.score, 3), "confidence": round(key.confidence, 3), "warning": key.warning},
                "warnings": warnings,
            }
            tmp = d / "processing.json.part"
            tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, d / "processing.json"); published.append(d / "processing.json")
        except BaseException:
            for p in published: p.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(work, ignore_errors=True)
            (d / "processing.json.part").unlink(missing_ok=True)
