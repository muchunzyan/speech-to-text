from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path


class MediaError(RuntimeError):
    """Raised when FFmpeg cannot prepare the input file."""


def require_ffmpeg() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        joined = ", ".join(missing)
        raise MediaError(f"Не найдены системные команды: {joined}. Установите FFmpeg.")


def extract_audio(
    source: Path,
    destination: Path,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Extract a mono 16 kHz PCM track suitable for Whisper."""
    require_ffmpeg()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while process.poll() is None:
        if is_cancelled and is_cancelled():
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            destination.unlink(missing_ok=True)
            raise InterruptedError("Подготовка аудио отменена")
        time.sleep(0.2)
    stdout, stderr = process.communicate()
    if process.returncode:
        details = (stderr or stdout or "неизвестная ошибка FFmpeg").strip()
        raise MediaError(f"Не удалось извлечь аудиодорожку: {details}")
    return destination

