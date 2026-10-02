import hashlib
from pathlib import Path
from ..application.separation import SeparationError

MODEL_FILENAME = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
# SHA-256 calculado no computador do usuario e igual ao informado por copia publica no Hugging Face.
MODEL_SHA256 = "5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa"
MODEL_INFO = {
    "name": "BS-Roformer-Viperx-1297",
    "file": MODEL_FILENAME,
    "sha256": MODEL_SHA256,
    "obtained_with": "audio-separator 0.47.0 (--download_model_only)",
    "license": "NAO VERIFICADA (pesos); audio-separator e MIT",
}

def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk): h.update(block)
    return h.hexdigest()

def verify_model(path, expected: str) -> str:
    p = Path(path)
    if not p.is_file(): raise SeparationError(f"modelo nao encontrado: {p}")
    got = sha256_file(p)
    if got != expected.lower():
        raise SeparationError(f"checksum do modelo diverge (esperado {expected.lower()[:12]}..., obtido {got[:12]}...)")
    return got
