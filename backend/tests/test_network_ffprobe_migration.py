import json, shutil, sqlite3, subprocess, sys, wave
import pytest
from types import SimpleNamespace as NS
from karaoke.domain.errors import UploadRejected
from karaoke.infrastructure import network as net
from karaoke.infrastructure.ffprobe_validator import FfprobeValidator
from karaoke.infrastructure.sqlite_store import SqliteStore, V1

PAIRS = [("Loopback", "127.0.0.1"), ("vEthernet (WSL)", "172.20.0.1"), ("Wi-Fi", "192.168.0.15"),
         ("Ethernet", "10.0.0.4"), ("Auto", "169.254.1.1")]

def test_classify_excludes_loopback_linklocal_and_sorts_virtual_last():
    r = net.classify(PAIRS)
    assert [i.ip for i in r] == ["10.0.0.4", "192.168.0.15", "172.20.0.1"]
    assert r[-1].virtual

def test_choose_and_preferred():
    r = net.classify(PAIRS)
    assert net.choose(r).ip == "10.0.0.4"
    assert net.choose(r, "192.168.0.15").name == "Wi-Fi"
    with pytest.raises(ValueError): net.choose(r, "1.2.3.4")
    assert net.choose([]) is None

@pytest.mark.parametrize("ip", ["127.0.0.1", "0.0.0.0"])
def test_build_url_refuses_local(ip):
    with pytest.raises(ValueError): net.build_url(ip, 8000)

def test_build_url_token_in_fragment():
    assert net.build_url("192.168.0.15", 8000, "tok") == "http://192.168.0.15:8000/#token=tok"

def test_diagnose():
    assert "Nenhuma interface" in net.diagnose([], None, 8000)[0]
    r = net.classify(PAIRS); msgs = net.diagnose(r, r[-1], 8000)
    assert any("virtual" in m for m in msgs) and any("New-NetFirewallRule" in m and "8000" in m for m in msgs)

def runner(out, rc=0):
    return lambda *a, **k: NS(returncode=rc, stdout=json.dumps(out) if isinstance(out, dict) else out, stderr="")

GOOD = {"format": {"format_name": "mp3", "duration": "123.4"}, "streams": [{"codec_type": "audio", "codec_name": "mp3"}]}

def test_ffprobe_ok():
    i = FfprobeValidator(runner=runner(GOOD)).probe("x", "mp3")
    assert i.duration_s == 123.4 and i.codec == "mp3"

def test_ffprobe_m4a_container_names():
    d = {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "60"}, "streams": [{"codec_type": "audio"}]}
    assert FfprobeValidator(runner=runner(d)).probe("x", "m4a").duration_s == 60

@pytest.mark.parametrize("out,rc,ext,code", [
    (GOOD, 0, "wav", "conteudo_extensao"),
    ({"format": {"format_name": "mp3", "duration": "9"}, "streams": [{"codec_type": "video"}]}, 0, "mp3", "sem_audio"),
    ({"format": {"format_name": "mp3"}, "streams": [{"codec_type": "audio"}]}, 0, "mp3", "duracao_indisponivel"),
    ("", 1, "mp3", "conteudo_invalido"),
    ("nao-json", 0, "mp3", "conteudo_invalido"),
])
def test_ffprobe_rejections(out, rc, ext, code):
    with pytest.raises(UploadRejected) as e: FfprobeValidator(runner=runner(out, rc)).probe("x", ext)
    assert e.value.code == code

def test_ffprobe_missing_binary():
    def r(*a, **k): raise FileNotFoundError
    with pytest.raises(UploadRejected) as e: FfprobeValidator(runner=r).probe("x", "mp3")
    assert e.value.code == "ffprobe_ausente"

@pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe nao instalado (teste de integracao real)")
def test_ffprobe_real_wav_and_fake_mp3(tmp_path):
    w = tmp_path / "a.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\x00\x00" * 8000)
    v = FfprobeValidator()
    assert 0.9 < v.probe(w, "wav").duration_s < 1.1
    with pytest.raises(UploadRejected): v.probe(w, "mp3")
    bad = tmp_path / "b.mp3"; bad.write_bytes(b"MZ\x90\x00 nao e audio")
    with pytest.raises(UploadRejected): v.probe(bad, "mp3")

def test_migration_from_module1_db(tmp_path):
    p = tmp_path / "old.db"
    c = sqlite3.connect(p); c.executescript(V1)
    c.execute("INSERT INTO songs VALUES('id1','Old','Art','NA_FILA',NULL,'2026-01-01')"); c.commit(); c.close()
    st = SqliteStore(p); s = st.get_song("id1")
    assert s.title == "Old" and s.sha256 is None and s.ext == ""
    assert st.db.execute("PRAGMA user_version").fetchone()[0] == 4
    SqliteStore(p)  # reabrir nao reaplica migracao

def test_store_regression_flow_and_recover(tmp_path):
    from karaoke.domain.states import State
    st = SqliteStore(tmp_path / "k.db"); a = st.create_song("a", "", None); b = st.create_song("b", "", None)
    ja, jb = st.enqueue(a.id, 3), st.enqueue(b.id, 3)
    assert (st.position(ja.id), st.position(jb.id)) == (1, 2)
    st.claim_next(); st.advance(ja.id, State.SEPARANDO_INSTRUMENTAL_VOCAIS)
    st2 = SqliteStore(tmp_path / "k.db"); r = st2.recover()
    assert r[0].state == State.NA_FILA and st2.get_song(a.id).status == State.NA_FILA
