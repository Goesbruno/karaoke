import json, subprocess
from ..application.media import MediaInfo
from ..domain.errors import UploadRejected

EXT_FORMATS = {
    "mp3": {"mp3"}, "wav": {"wav"}, "flac": {"flac"}, "ogg": {"ogg"},
    "m4a": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
}

class FfprobeValidator:
    def __init__(self, ffprobe_path="ffprobe", runner=subprocess.run, timeout=30):
        self.path, self.runner, self.timeout = ffprobe_path, runner, timeout

    def probe(self, path, ext):
        cmd = [self.path, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
        try:
            r = self.runner(
    cmd,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=self.timeout,
)
        except FileNotFoundError:
            raise UploadRejected("ffprobe_ausente", "ffprobe nao encontrado; instale o FFmpeg e ajuste KARAOKE_FFPROBE_PATH")
        except subprocess.TimeoutExpired:
            raise UploadRejected("conteudo_invalido", "tempo esgotado ao analisar o arquivo")
        if r.returncode != 0:
            raise UploadRejected("conteudo_invalido", "arquivo nao e um audio valido")
        try:
            data = json.loads(r.stdout)
        except ValueError:
            raise UploadRejected("conteudo_invalido", "resposta invalida do ffprobe")
        fmt = data.get("format", {})
        names = frozenset(n for n in str(fmt.get("format_name", "")).split(",") if n)
        if not names & EXT_FORMATS.get(ext, set()):
            raise UploadRejected("conteudo_extensao", f"conteudo ({','.join(sorted(names)) or '?'}) nao corresponde a extensao .{ext}")
        audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
        if not audio:
            raise UploadRejected("sem_audio", "nenhuma faixa de audio encontrada")
        try:
            dur = float(fmt.get("duration"))
        except (TypeError, ValueError):
            raise UploadRejected("duracao_indisponivel", "duracao nao pode ser determinada")
        return MediaInfo(dur, names, audio[0].get("codec_name", ""))
