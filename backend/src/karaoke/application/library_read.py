import json
from dataclasses import dataclass
from pathlib import Path
from ..domain.states import State

STEMS = ("instrumental.wav", "vocals.wav")

@dataclass(frozen=True)
class LibraryView:
    ready: bool
    issues: tuple[str, ...]
    key_estimated: str | None
    key_confidence: float | None
    key_warning: str
    lead_backing_available: bool
    lead_backing_reason: str
    lyrics_status: str = "SEM_LETRA"

    def as_dict(self):
        return {"ready": self.ready, "issues": list(self.issues),
                "key_estimated": self.key_estimated, "key_confidence": self.key_confidence,
                "key_warning": self.key_warning, "lead_backing_available": self.lead_backing_available,
                "lead_backing_reason": self.lead_backing_reason, "lyrics_status": self.lyrics_status}

class LibraryReader:
    """Somente leitura; nunca remove nem modifica arquivos durante a conciliacao."""
    def __init__(self, files): self.files = files

    def read(self, song):
        d = self.files.song_dir(song.id)
        problems = []
        if song.status != State.CONCLUIDA:
            return LibraryView(False, (), None, None, "", False, "Ainda nao processada")
        if not d.is_dir() or d.is_symlink():
            return LibraryView(False, ("pasta_ausente",), None, None, "", False, "Pasta ausente")
        expected = d / f"original.{song.ext}" if song.ext else None
        if not expected or not expected.is_file() or expected.is_symlink() or expected.stat().st_size == 0:
            problems.append("original_ausente")
        for name in STEMS:
            p = d / name
            if not p.is_file() or p.is_symlink() or p.stat().st_size == 0:
                problems.append(f"{name}_ausente")
        meta = d / "processing.json"
        doc = {}
        if not meta.is_file() or meta.is_symlink():
            problems.append("processing_json_ausente")
        else:
            try:
                if meta.stat().st_size > 1_000_000: raise ValueError("metadados grandes demais")
                doc = json.loads(meta.read_text(encoding="utf-8"))
                if not isinstance(doc, dict) or doc.get("schema") != 1:
                    raise ValueError("schema invalido")
                declared = doc.get("stems", [])
                if not isinstance(declared, list) or not set(STEMS).issubset(declared):
                    raise ValueError("stems essenciais nao declarados")
            except (OSError, ValueError, UnicodeError, TypeError):
                problems.append("processing_json_invalido"); doc = {}
        key = doc.get("key") if isinstance(doc.get("key"), dict) else {}
        lb = doc.get("lead_backing") if isinstance(doc.get("lead_backing"), dict) else {}
        declared = doc.get("stems") if isinstance(doc.get("stems"), list) else []
        extra_ready = bool(lb.get("available"))
        if extra_ready:
            for name in ("lead.wav", "backing.wav"):
                p = d / name
                if name not in declared or not p.is_file() or p.is_symlink() or p.stat().st_size == 0:
                    extra_ready = False
        reason = lb.get("reason", "") if not extra_ready else ""
        if lb.get("available") and not extra_ready:
            reason = "Lead/backing declarados, mas arquivos indisponiveis"
        return LibraryView(not problems, tuple(problems), key.get("estimated"), key.get("confidence"),
                           key.get("warning", ""), extra_ready, reason)
