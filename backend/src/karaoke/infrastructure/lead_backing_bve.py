"""Segundo estágio: saída complementar BVE = lead; saída principal BVE = backing."""
from pathlib import Path
from ..application.separation import SeparationError


class BveLeadBacking:
    def __init__(self, separator, model_file: str, model_sha256: str):
        self.separator = separator
        self.model_file = model_file
        self.model_sha256 = model_sha256

    def split(self, vocals: Path, out_dir: Path):
        result = self.separator.separate(vocals, out_dir)
        lead, backing = result.instrumental, result.vocals
        if lead == backing:
            raise SeparationError("BVE retornou o mesmo arquivo para lead e backing")
        return lead, backing, {
            "model": self.model_file,
            "sha256": self.model_sha256,
            "mapping": {
                "lead": "Instrumental (saida complementar do BVE)",
                "backing": "Vocals (saida principal do BVE)",
            },
            "separation": result.meta,
        }
