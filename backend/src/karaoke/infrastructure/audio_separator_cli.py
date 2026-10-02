import os, re, shutil, subprocess
from pathlib import Path
from ..application.separation import OutOfMemory, SeparationError, SeparationResult

OOM_MARKERS = ("out of memory", "cuda error: out of memory", "cublas_status_alloc_failed", "not enough memory")

class AudioSeparatorCli:
    """Chama o executavel audio-separator (ambiente isolado e validado) em um subprocesso.
    Isola memoria/VRAM do worker, permite timeout e repetir com parametros menores ou na CPU."""
    def __init__(self, cmd, model_dir, model_file, overlap=2, segment_size=None, batch_size=1, autocast=False,
                 timeout_s=3600, cpu_fallback=True, reduced_segments=(128, 64), runner=subprocess.run):
        self.cmd, self.model_dir, self.model_file = cmd, Path(model_dir), model_file
        self.overlap, self.segment_size, self.batch_size, self.autocast = overlap, segment_size, batch_size, autocast
        self.timeout_s, self.cpu_fallback, self.reduced, self.runner = timeout_s, cpu_fallback, tuple(reduced_segments), runner

    def _attempts(self):
        a = [("gpu", self.segment_size, False)]
        a += [(f"gpu-segmento-{s}", s, False) for s in self.reduced if s != self.segment_size]
        if self.cpu_fallback: a.append(("cpu", self.segment_size, True))
        return a

    def _command(self, wav, out_dir, seg):
        python_exe = Path(self.cmd).with_name("python.exe")
        c = [str(python_exe), "-c", "from audio_separator.utils.cli import main; main()",
     str(wav), "-m", self.model_file, "--model_file_dir", str(self.model_dir),
             "--output_format", "WAV", "--output_dir", str(out_dir),
             "--mdxc_overlap", str(self.overlap), "--mdxc_batch_size", str(self.batch_size)]
        if seg: c += ["--mdxc_segment_size", str(seg), "--mdxc_override_model_segment_size"]
        if self.autocast: c.append("--use_autocast")
        return c

    def separate(self, wav: Path, out_dir: Path) -> SeparationResult:
        last_oom = ""
        for label, seg, cpu in self._attempts():
            shutil.rmtree(out_dir, ignore_errors=True); Path(out_dir).mkdir(parents=True)
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            if cpu: env["CUDA_VISIBLE_DEVICES"] = "-1"
            cmd = self._command(wav, out_dir, seg)
            try:
                r = self.runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=self.timeout_s, env=env)
            except FileNotFoundError:
                raise SeparationError(f"executavel do separador nao encontrado: {self.cmd} (KARAOKE_SEPARATOR_CMD)")
            except subprocess.TimeoutExpired:
                raise SeparationError(f"tempo esgotado na separacao ({self.timeout_s}s)")
            text = f"{r.stdout or ''}\n{r.stderr or ''}"
            if r.returncode != 0:
                if any(m in text.lower() for m in OOM_MARKERS):
                    last_oom = f"falta de memoria na tentativa '{label}'"; continue
                raise SeparationError(f"separador falhou (codigo {r.returncode}): {text.strip()[-400:]}")
            by_stem = {"Vocals": [], "Instrumental": []}
            for path in Path(out_dir).glob("*.wav"):
                tags = re.findall(r"\((Vocals|Instrumental)\)", path.stem)
                if tags:
                    by_stem[tags[-1]].append(path)
            voc = sorted(by_stem["Vocals"])
            ins = sorted(by_stem["Instrumental"])
            if len(voc) != 1 or len(ins) != 1:
                found = sorted(p.name for p in Path(out_dir).iterdir() if p.is_file())
                raise SeparationError(
                    "saidas de vocais/instrumental nao encontradas ou ambiguas: "
                    f"{found[:10]!r}"
                )
            ver = re.search(r"Separator version ([\w.]+)", text)
            dev = re.search(r"Torch device to (\w+)", text)
            return SeparationResult(ins[0], voc[0], {
                "attempt": label, "tool": "audio-separator", "tool_version": ver.group(1) if ver else "?",
                "device": "CPU" if cpu else (dev.group(1) if dev else "?"),
                "params": {"overlap": self.overlap, "segment_size": seg, "batch_size": self.batch_size,
                           "autocast": self.autocast, "model": self.model_file},
            })
        raise OutOfMemory(f"sem memoria em todas as tentativas ({last_oom})")