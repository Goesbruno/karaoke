"""Download de áudio do YouTube usando yt-dlp.

Encapsula a chamada à biblioteca yt-dlp, converte para MP3 e retorna
o caminho do arquivo gerado. O arquivo resultante é consumido pelo
fluxo de upload existente, como se tivesse vindo de um UploadFile.
"""

import os
import tempfile
from pathlib import Path
import yt_dlp


class YouTubeDownloadError(Exception):
    """Falha ao baixar ou converter o áudio do YouTube."""
    pass


def download_audio_from_youtube(video_url: str, output_dir: str | Path) -> Path:
    """Baixa o áudio de um vídeo do YouTube e o converte para MP3.

    Args:
        video_url: URL completa do vídeo (ex: https://www.youtube.com/watch?v=...).
        output_dir: Diretório onde o arquivo MP3 será salvo.

    Returns:
        Path do arquivo MP3 gerado.

    Raises:
        YouTubeDownloadError: se o download ou a conversão falharem.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Template de saída: usa o título do vídeo como nome base
    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        # Embute metadados e capa (opcional, mas útil para karaokê)
        "writethumbnail": True,
        "embedthumbnail": True,
        "addmetadata": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            filename = ydl.prepare_filename(info)
            # O yt-dlp substitui a extensão para .mp3 após o postprocessor
            final_path = Path(os.path.splitext(filename)[0] + ".mp3")

            ydl.download([video_url])

            if not final_path.is_file():
                raise YouTubeDownloadError(
                    f"Arquivo MP3 não foi gerado: {final_path}"
                )
            return final_path

    except yt_dlp.utils.DownloadError as e:
        raise YouTubeDownloadError(f"Falha no download: {e}") from e
    except Exception as e:
        raise YouTubeDownloadError(f"Erro inesperado ao baixar áudio: {e}") from e