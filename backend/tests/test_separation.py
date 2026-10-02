import json, math, wave
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import pytest
from karaoke.application.separation import (KeyResult, OutOfMemory, ProcessingPipeline, SeparationError,
                                            SeparationResult, WavInfo, check_stem)
from karaoke.domain.states import State
from karaoke.infrastructure.audio_separator_cli import AudioSeparatorCli
from karaoke.infrastructure.ffmpeg_preparer import FfmpegPreparer
from karaoke.infrastructure.key_estimator import MAJOR, MINOR, NAMES, NumpyKeyEstimator
from karaoke.infrastructure.model_manifest import MODEL_SHA256, sha256_file, verify_model
from karaoke.infrastructure.wav_tools import WavInspector

SID = "11111111-1111-4111-8111-111111111111"

def write_wav(path, seconds=1.0, sr=44100, ch=2, amp=8000, freq=440.0):
    t = np.arange(int(seconds * sr)) / sr
    x = np.clip(amp * np.sin(2 * math.pi * freq * t), -32768, 32767).astype(np.int16)
    data = np.repeat(x[:, None], ch, axis=1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes(data.tobytes())

class Prep:
    def to_wav(self, src, dst): write_wav(dst)

class Sep:
    def __init__(self, **kw): self.kw = kw
    def separate(self, wav, out_dir):
        i, v = Path(out_dir) / "i.wav", Path(out_dir) / "v.wav"
        write_wav(i, **self.kw.get("i", {})); write_wav(v, **self.kw.get("v", {}))
        return SeparationResult(i, v, {"attempt": "gpu"})

class Key:
    def estimate(self, wav): return KeyResult("C maior", 0.8, 0.9)

class BoomKey:
    def estimate(self, wav): raise RuntimeError("x")

class LB:
    def split(self, vocals, out_dir):
        l, b = Path(out_dir) / "l.wav", Path(out_dir) / "b.wav"; write_wav(l); write_wav(b)
        return l, b, {"model": "fake"}

@pytest.fixture
def song(tmp_path):
    d = tmp_path / SID; d.mkdir(); (d / "original.mp3").write_bytes(b"x"); return d

def pipe(d, sep=None, key=None, lb=None):
    return ProcessingPipeline(lambda _: d, Prep(), sep or Sep(), key or Key(), WavInspector(), lb, {"name": "m"}, 0.1)

def run(p):
    steps = []
    p.run(NS(song_id=SID), lambda st, msg="": steps.append(st))
    return steps

def test_success_publishes_atomically_and_records_metadata(song):
    steps = run(pipe(song))
    assert steps == [State.SEPARANDO_INSTRUMENTAL_VOCAIS, State.ANALISANDO]
    assert (song / "instrumental.wav").exists() and (song / "vocals.wav").exists()
    meta = json.loads((song / "processing.json").read_text(encoding="utf-8"))
    assert meta["lead_backing"]["available"] is False and meta["model"] == {"name": "m"}
    assert meta["key"]["estimated"] == "C maior" and meta["input"]["sample_rate"] == 44100
    assert not (song / ".work").exists() and not list(song.glob("*.part"))

def test_lead_backing_step_when_configured(song):
    steps = run(pipe(song, lb=LB()))
    assert State.SEPARANDO_LEAD_BACKING in steps and (song / "lead.wav").exists() and (song / "backing.wav").exists()

@pytest.mark.parametrize("kw,msg", [
    ({"i": {"seconds": 2.0}}, "duracao"),
    ({"v": {"sr": 22050}}, "taxa"),
    ({"i": {"ch": 1}}, "canais"),
    ({"i": {"amp": 0}}, "silencioso"),
])
def test_invalid_stems_publish_nothing(song, kw, msg):
    with pytest.raises(SeparationError, match=msg): run(pipe(song, sep=Sep(**kw)))
    assert not (song / "instrumental.wav").exists() and not (song / "processing.json").exists()
    assert not (song / ".work").exists()

def test_silent_vocals_is_only_warning(song):
    run(pipe(song, sep=Sep(v={"amp": 0})))
    assert any("vocals silencioso" in w for w in json.loads((song / "processing.json").read_text(encoding="utf-8"))["warnings"])

def test_separator_failure_cleans(song):
    class Bad:
        def separate(self, *a): raise OutOfMemory("x")
    with pytest.raises(OutOfMemory): run(pipe(song, sep=Bad()))
    assert sorted(p.name for p in song.iterdir()) == ["original.mp3"]

def test_key_failure_does_not_invent_key(song):
    run(pipe(song, key=BoomKey()))
    m = json.loads((song / "processing.json").read_text(encoding="utf-8"))
    assert m["key"]["estimated"] is None and any("tom falhou" in w for w in m["warnings"])

def test_missing_original(tmp_path):
    d = tmp_path / SID; d.mkdir()
    with pytest.raises(SeparationError, match="original"): run(pipe(d))

def test_check_stem_tolerance():
    ref = WavInfo(44100, 2, 44100, 100)
    assert check_stem("v", WavInfo(44100, 2, 44100 + 2000, 100), ref, 0.1) == []
    with pytest.raises(SeparationError): check_stem("v", WavInfo(44100, 2, 44100 + 9000, 100), ref, 0.1)

# ---- CLI (subprocesso simulado) ----
def fake_runner(script, calls):
    def r(cmd, **kw):
        calls.append((cmd, kw.get("env", {})))
        out = Path(cmd[cmd.index("--output_dir") + 1]); step = script[len(calls) - 1]
        if step == "ok":
            (out / "x_(Vocals)_m.wav").write_bytes(b"v"); (out / "x_(Instrumental)_m.wav").write_bytes(b"i")
            return NS(returncode=0, stdout="Separator version 0.47.0 ...\nsetting Torch device to CUDA\n", stderr="")
        if step == "oom": return NS(returncode=1, stdout="", stderr="torch.OutOfMemoryError: CUDA out of memory")
        return NS(returncode=1, stdout="", stderr="Traceback: boom")
    return r

def cli(script, **kw):
    calls = []
    return AudioSeparatorCli("sep.exe", "models", "m.ckpt", runner=fake_runner(script, calls), **kw), calls

def test_cli_first_attempt_uses_measured_params(tmp_path):
    s, calls = cli(["ok"]); r = s.separate(Path("in.wav"), tmp_path / "o")
    cmd, env = calls[0]
    assert cmd[cmd.index("--mdxc_overlap") + 1] == "2" and "--use_autocast" not in cmd and "--mdxc_override_model_segment_size" not in cmd
    assert env.get("CUDA_VISIBLE_DEVICES") != "-1"
    assert r.meta["tool_version"] == "0.47.0" and r.meta["device"] == "CUDA" and r.meta["attempt"] == "gpu"

def test_cli_oom_ladder_reduces_segment_then_cpu(tmp_path):
    s, calls = cli(["oom", "oom", "oom", "ok"]); r = s.separate(Path("in.wav"), tmp_path / "o")
    assert "--mdxc_segment_size" in calls[1][0] and calls[1][0][calls[1][0].index("--mdxc_segment_size") + 1] == "128"
    assert calls[2][0][calls[2][0].index("--mdxc_segment_size") + 1] == "64"
    assert calls[3][1]["CUDA_VISIBLE_DEVICES"] == "-1" and r.meta["attempt"] == "cpu" and r.meta["device"] == "CPU"

def test_cli_recovers_on_second_attempt(tmp_path):
    s, calls = cli(["oom", "ok"]); assert s.separate(Path("in.wav"), tmp_path / "o").meta["attempt"] == "gpu-segmento-128"

def test_cli_non_oom_error_does_not_retry(tmp_path):
    s, calls = cli(["err"])
    with pytest.raises(SeparationError, match="boom"): s.separate(Path("in.wav"), tmp_path / "o")
    assert len(calls) == 1

def test_cli_all_oom_without_cpu(tmp_path):
    s, calls = cli(["oom", "oom", "oom"], cpu_fallback=False)
    with pytest.raises(OutOfMemory): s.separate(Path("in.wav"), tmp_path / "o")
    assert len(calls) == 3

def test_cli_missing_outputs_timeout_and_binary(tmp_path):
    import subprocess
    s = AudioSeparatorCli("sep", "m", "f", runner=lambda c, **k: NS(returncode=0, stdout="", stderr=""))
    with pytest.raises(SeparationError, match="nao encontradas"): s.separate(Path("i"), tmp_path / "o")
    def to(c, **k): raise subprocess.TimeoutExpired(c, 1)
    with pytest.raises(SeparationError, match="tempo"): AudioSeparatorCli("s", "m", "f", runner=to).separate(Path("i"), tmp_path / "o")
    def nf(c, **k): raise FileNotFoundError
    with pytest.raises(SeparationError, match="executavel"): AudioSeparatorCli("s", "m", "f", runner=nf).separate(Path("i"), tmp_path / "o")

def test_ffmpeg_preparer_command_and_errors(tmp_path):
    seen = []
    def ok(cmd, **k): seen.append(cmd); Path(cmd[-1]).write_bytes(b"x"); return NS(returncode=0, stderr="")
    FfmpegPreparer("ff", runner=ok).to_wav(Path("a.mp3"), tmp_path / "o.wav")
    assert "44100" in seen[0] and "pcm_s16le" in seen[0] and seen[0][0] == "ff"
    with pytest.raises(SeparationError): FfmpegPreparer(runner=lambda c, **k: NS(returncode=1, stderr="bad")).to_wav(Path("a"), tmp_path / "z.wav")

# ---- modelo e WAV ----
def test_verify_model(tmp_path):
    p = tmp_path / "m.ckpt"; p.write_bytes(b"abc"); h = sha256_file(p)
    assert verify_model(p, h.upper()) == h
    with pytest.raises(SeparationError, match="diverge"): verify_model(p, MODEL_SHA256)
    with pytest.raises(SeparationError, match="nao encontrado"): verify_model(tmp_path / "x", h)

def test_wav_inspector(tmp_path):
    write_wav(tmp_path / "a.wav", amp=50000, seconds=0.5)
    i = WavInspector().inspect(tmp_path / "a.wav")
    assert (i.sample_rate, i.channels, i.frames) == (44100, 2, 22050) and i.peak >= 32767 and i.clip_ratio > 0
    (tmp_path / "b.wav").write_bytes(b"nao e wav")
    with pytest.raises(SeparationError): WavInspector().inspect(tmp_path / "b.wav")

# ---- tom (sinteticos: testam o algoritmo, nao a acuracia em musica real) ----
def synth_key(path, tonic, minor, sr=22050, seconds=12):
    prof = MINOR if minor else MAJOR
    t = np.arange(sr * seconds) / sr
    x = sum(prof[(pc - tonic) % 12] * np.sin(2 * math.pi * 440 * 2 ** ((60 + pc - 69) / 12) * t) for pc in range(12))
    x = (x / np.abs(x).max() * 12000).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())

@pytest.mark.parametrize("tonic,minor", [(0, False), (7, False), (3, True), (9, True), (10, False)])
def test_key_estimator_recovers_synthetic_keys(tmp_path, tonic, minor):
    synth_key(tmp_path / "k.wav", tonic, minor)
    r = NumpyKeyEstimator().estimate(tmp_path / "k.wav")
    assert r.key == f"{NAMES[tonic]} {'menor' if minor else 'maior'}" and r.score > 0.85

def test_key_estimator_inconclusive_cases(tmp_path):
    write_wav(tmp_path / "s.wav", seconds=8, amp=0)
    assert NumpyKeyEstimator().estimate(tmp_path / "s.wav").key is None
    write_wav(tmp_path / "c.wav", seconds=2)
    assert "curto" in NumpyKeyEstimator().estimate(tmp_path / "c.wav").warning
    sr = 22050; t = np.arange(sr * 10) / sr
    x = sum(np.sin(2 * math.pi * 440 * 2 ** ((60 + pc - 69) / 12) * t) for pc in range(12))
    x = (x / np.abs(x).max() * 12000).astype(np.int16)
    with wave.open(str(tmp_path / "f.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())
    r = NumpyKeyEstimator().estimate(tmp_path / "f.wav")
    assert r.key is None and r.warning


def test_bve_maps_complement_to_lead_and_primary_to_backing(tmp_path):
    from karaoke.infrastructure.lead_backing_bve import BveLeadBacking
    lead = tmp_path / "vocals_(Instrumental)_UVR-BVE-4B_SN-44100-1.wav"
    backing = tmp_path / "vocals_(Vocals)_UVR-BVE-4B_SN-44100-1.wav"
    class FakeBve:
        def separate(self, vocals, out_dir):
            assert vocals.name == "vocals.wav"
            return SeparationResult(lead, backing, {"attempt": "gpu"})
    splitter = BveLeadBacking(FakeBve(), "UVR-BVE-4B_SN-44100-1.pth", "hash")
    got_lead, got_backing, meta = splitter.split(tmp_path / "vocals.wav", tmp_path / "out")
    assert got_lead == lead and got_backing == backing
    assert meta["mapping"]["lead"].startswith("Instrumental")
    assert meta["mapping"]["backing"].startswith("Vocals")


def test_bve_rejects_identical_outputs(tmp_path):
    from karaoke.infrastructure.lead_backing_bve import BveLeadBacking
    class FakeBve:
        def separate(self, vocals, out_dir):
            p = tmp_path / "same.wav"
            return SeparationResult(p, p)
    with pytest.raises(SeparationError, match="mesmo arquivo"):
        BveLeadBacking(FakeBve(), "bve.pth", "hash").split(tmp_path / "vocals.wav", tmp_path / "out")


@pytest.mark.parametrize("input_name,model_name,output_model", [
    ("input.wav", "actual_checkpoint.ckpt", "friendly_label"),
    ("input_(Vocals)_first.wav", "UVR-BVE-4B_SN-44100-1.pth", "UVR-BVE-4B_SN-44100-1"),
])
def test_cli_resolves_last_stem_tag_without_assuming_output_model_name(tmp_path, input_name, model_name, output_model):
    def runner(cmd, **kwargs):
        out = Path(cmd[cmd.index("--output_dir") + 1])
        prefix = Path(input_name).stem
        (out / f"{prefix}_(Instrumental)_{output_model}.wav").write_bytes(b"instrumental")
        (out / f"{prefix}_(Vocals)_{output_model}.wav").write_bytes(b"vocals")
        return NS(returncode=0, stdout="", stderr="")
    sep = AudioSeparatorCli("sep.exe", "models", model_name, runner=runner)
    result = sep.separate(tmp_path / input_name, tmp_path / "out")
    assert result.instrumental.read_bytes() == b"instrumental"
    assert result.vocals.read_bytes() == b"vocals"
