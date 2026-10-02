"""Worker em processo separado (fila persistente, 1 trabalho por vez)."""
import sys, time
from typing import Protocol
from ..config import Settings
from ..domain.states import State
from ..infrastructure.sqlite_store import SqliteStore

class Processor(Protocol):
    def run(self, job, advance) -> None: ...

class NotImplementedProcessor:
    def run(self, job, advance):
        raise NotImplementedError("processador nao configurado")

def run_once(store, processor: Processor) -> bool:
    job = store.claim_next()
    if not job: return False
    try:
        processor.run(job, lambda st, msg="": store.advance(job.id, st, message=msg))
        store.advance(job.id, State.CONCLUIDA, message="ok")
    except Exception as e:  # falha nunca vira CONCLUIDA
        store.fail(job.id, f"{type(e).__name__}: {e}")
    return True

def build_processor(settings: Settings, files):
    from ..application.separation import ProcessingPipeline
    from ..infrastructure.audio_separator_cli import AudioSeparatorCli
    from ..infrastructure.lead_backing_bve import BveLeadBacking
    from ..infrastructure.ffmpeg_preparer import FfmpegPreparer
    from ..infrastructure.key_estimator import NumpyKeyEstimator
    from ..infrastructure.model_manifest import MODEL_INFO, verify_model
    from ..infrastructure.wav_tools import WavInspector
    from ..separation_config import SeparatorSettings
    try:
        ss = SeparatorSettings.from_env()
    except ValueError as exc:
        from ..application.separation import SeparationError
        raise SeparationError(str(exc)) from exc
    from ..application.separation import SeparationError
    from pathlib import Path
    exe = Path(ss.cmd)
    python_exe = exe.with_name("python.exe" if exe.suffix.lower() == ".exe" else "python")
    if not exe.is_file() or not python_exe.is_file():
        raise SeparationError(f"Ambiente local do separador incompleto: {exe} / {python_exe}")
    verify_model(ss.model_dir / ss.model_file, ss.model_sha256)
    sep = AudioSeparatorCli(ss.cmd, ss.model_dir, ss.model_file, ss.overlap, ss.segment_size, ss.batch_size,
                            ss.autocast, ss.timeout_s, ss.cpu_fallback, ss.reduced_segments)
    bve_file = ss.bve_model_file
    bve_sha256 = ss.bve_model_sha256
    verify_model(ss.model_dir / bve_file, bve_sha256)
    bve_separator = AudioSeparatorCli(
        ss.cmd, ss.model_dir, bve_file,
        timeout_s=ss.timeout_s,
        cpu_fallback=ss.cpu_fallback,
        reduced_segments=(),
    )
    lead_backing = BveLeadBacking(bve_separator, bve_file, bve_sha256)
    return ProcessingPipeline(files.song_dir, FfmpegPreparer(ss.ffmpeg_path), sep, NumpyKeyEstimator(),
                              WavInspector(), lead_backing, {**MODEL_INFO, "sha256": ss.model_sha256}, ss.tolerance_s)

def main():
    from ..application.separation import SeparationError
    from ..infrastructure.local_files import LocalFileStore
    s = Settings.from_env()
    # Mesmo terminal iniciado fora da raiz deve usar o banco local do projeto.
    from ..separation_config import ROOT
    if not s.data_dir.is_absolute():
        s.data_dir = (ROOT / s.data_dir).resolve()
    store, files = SqliteStore(s.db_path), LocalFileStore(s.data_dir)
    store.recover()
    if s.max_gpu_jobs != 1:
        print("Aviso: este worker processa 1 trabalho por vez; KARAOKE_MAX_GPU_JOBS != 1 e ignorado.")
    try:
        proc = build_processor(s, files)
    except SeparationError as e:
        print(f"Worker nao iniciado: {e}"); sys.exit(2)
    print("Worker pronto. Aguardando trabalhos...")
    while True:
        if not run_once(store, proc):
            time.sleep(2)

if __name__ == "__main__":
    main()
