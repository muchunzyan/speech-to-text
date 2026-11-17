from __future__ import annotations

import importlib.util
import io
import multiprocessing
import queue
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
from tqdm.auto import tqdm

from transcriber.exporters import normalize_segments, write_exports
from transcriber.media import extract_audio
from transcriber.models import (
    default_model_cache_directory,
    find_cached_model,
    get_model_profile,
    inference_engine,
    model_repository,
)

ProgressCallback = Callable[[str, int, str], None]
CancelCallback = Callable[[], bool]

# Long recordings are decoded in ~30-second windows. Reusing the previous window as a prompt can
# make a single mistaken phrase feed itself indefinitely. OpenAI Whisper documents disabling this
# option as the primary mitigation for repetition loops. A slightly stricter compression threshold
# also triggers temperature fallback earlier for highly repetitive output.
WHISPER_DECODING_OPTIONS: dict[str, Any] = {
    "condition_on_previous_text": False,
    "compression_ratio_threshold": 2.0,
}


class TranscriptionCancelled(RuntimeError):
    """Raised when the user cancels an active job."""


@dataclass(frozen=True, slots=True)
class TranscriptionRequest:
    source: Path
    original_name: str
    output_dir: Path
    model_profile: str = "balanced"
    language: str | None = "ru"
    initial_prompt: str | None = None
    offline: bool = False
    is_cancelled: CancelCallback | None = None
    model_cache_dir: Path = field(default_factory=default_model_cache_directory)


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    language: str | None
    segments: list[dict[str, Any]]
    files: dict[str, Path]


def _format_bytes(value: float) -> str:
    size = float(value)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            return f"{size:.1f} {unit}" if unit != "Б" else f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} ГБ"


def _format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _transcribe_in_child(
    audio_path: str,
    model_path: str,
    language: str | None,
    initial_prompt: str | None,
    engine: str,
    result_queue: Any,
) -> None:
    """Run inference in a child process so an active job can be cancelled."""
    try:
        if engine == "mlx":
            raw_result = _transcribe_with_mlx(
                audio_path, model_path, language, initial_prompt, result_queue
            )
        elif engine == "ctranslate2":
            raw_result = _transcribe_with_faster_whisper(
                audio_path, model_path, language, initial_prompt, result_queue
            )
        else:
            raise RuntimeError(f"Неизвестный движок распознавания: {engine}")
        result_queue.put(
            {
                "event": "result",
                "ok": True,
                "text": str(raw_result.get("text", "")).strip(),
                "language": raw_result.get("language") or language,
                "segments": normalize_segments(raw_result.get("segments")),
            }
        )
    except Exception as exc:
        result_queue.put(
            {"event": "result", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        )


def _transcribe_with_mlx(
    audio_path: str,
    model_path: str,
    language: str | None,
    initial_prompt: str | None,
    result_queue: Any,
) -> dict[str, Any]:
    import mlx.core as mx
    import mlx_whisper
    from mlx_whisper.load_models import load_model
    from mlx_whisper.transcribe import ModelHolder

    model = load_model(model_path, dtype=mx.float16)
    ModelHolder.model = model
    ModelHolder.model_path = model_path
    result_queue.put({"event": "model_loaded"})
    kwargs: dict[str, Any] = {
        "path_or_hf_repo": model_path,
        "verbose": None,
        **WHISPER_DECODING_OPTIONS,
    }
    if language:
        kwargs["language"] = language
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    return mlx_whisper.transcribe(audio_path, **kwargs)


def _transcribe_with_faster_whisper(
    audio_path: str,
    model_path: str,
    language: str | None,
    initial_prompt: str | None,
    result_queue: Any,
) -> dict[str, Any]:
    import ctranslate2
    from faster_whisper import WhisperModel

    device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    try:
        model = WhisperModel(model_path, device=device, compute_type=compute_type)
    except (OSError, RuntimeError):
        if device != "cuda":
            raise
        # A driver can expose an NVIDIA GPU while optional CUDA/cuDNN DLLs are missing.
        # Keep the application usable by falling back to the always-available CPU backend.
        device = "cpu"
        compute_type = "int8"
        model = WhisperModel(model_path, device=device, compute_type=compute_type)
    result_queue.put(
        {"event": "model_loaded", "device": device, "compute_type": compute_type}
    )
    kwargs: dict[str, Any] = {
        "condition_on_previous_text": WHISPER_DECODING_OPTIONS[
            "condition_on_previous_text"
        ],
        "compression_ratio_threshold": WHISPER_DECODING_OPTIONS[
            "compression_ratio_threshold"
        ],
    }
    if language:
        kwargs["language"] = language
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    segment_iterator, info = model.transcribe(audio_path, **kwargs)
    segments = [
        {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
        }
        for segment in segment_iterator
    ]
    return {
        "text": "".join(str(segment["text"]) for segment in segments).strip(),
        "language": info.language or language,
        "segments": segments,
    }


def _download_model_in_child(repository: str, cache_dir: str, result_queue: Any) -> None:
    """Download a model in an isolated process so a stalled transfer can be killed."""

    class DownloadTqdm(tqdm):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["file"] = io.StringIO()
            kwargs["leave"] = False
            super().__init__(*args, **kwargs)

        def update(self, n: int | float | None = 1) -> bool | None:
            result = super().update(n)
            with suppress(queue.Full):
                result_queue.put_nowait(
                    {
                        "event": "progress",
                        "downloaded": float(self.n),
                        "total": float(self.total or 0),
                    }
                )
            return result

    try:
        model_path = snapshot_download(
            repo_id=repository,
            cache_dir=cache_dir,
            tqdm_class=DownloadTqdm,
            max_workers=4,
        )
        result_queue.put({"event": "result", "ok": True, "path": model_path})
    except Exception as exc:
        result_queue.put(
            {"event": "result", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        )


class LocalWhisperTranscriber:
    @staticmethod
    def _cancelled(request: TranscriptionRequest) -> bool:
        return bool(request.is_cancelled and request.is_cancelled())

    def _check_cancelled(self, request: TranscriptionRequest) -> None:
        if self._cancelled(request):
            raise TranscriptionCancelled("Транскрипция отменена")

    def _ensure_model(
        self,
        request: TranscriptionRequest,
        progress: ProgressCallback,
    ) -> Path:
        profile = get_model_profile(request.model_profile)
        repository = model_repository(profile)
        cached = find_cached_model(repository, request.model_cache_dir)
        if cached is not None:
            progress(
                "loading_model",
                30,
                f"{profile.model_name} уже скачана — загружаем её с диска",
            )
            return cached
        if request.offline:
            raise RuntimeError(
                f"{profile.model_name} не скачана, а приложение запущено в офлайн-режиме. "
                f"Выполните: transcriber models download {profile.key}"
            )

        progress(
            "downloading_model",
            20,
            f"Скачиваем {profile.model_name} ({profile.size_hint}). Это требуется только один раз.",
        )
        model_path = self._download_model(request, progress)
        self._check_cancelled(request)
        progress("loading_model", 30, f"{profile.model_name} скачана — загружаем модель")
        return Path(model_path)

    def _download_model(
        self,
        request: TranscriptionRequest,
        progress: ProgressCallback,
    ) -> Path:
        profile = get_model_profile(request.model_profile)
        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue(maxsize=64)
        process = context.Process(
            target=_download_model_in_child,
            args=(model_repository(profile), str(request.model_cache_dir), result_queue),
            name="model-download",
        )
        process.start()
        started_at = time.monotonic()
        last_report = 0.0
        payload: dict[str, Any] | None = None
        try:
            while process.is_alive():
                if self._cancelled(request):
                    process.terminate()
                    process.join(timeout=3)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=1)
                    raise TranscriptionCancelled("Скачивание модели отменено")
                try:
                    while True:
                        event = result_queue.get_nowait()
                        if event.get("event") == "result":
                            payload = event
                        elif event.get("event") == "progress":
                            downloaded = max(last_report, float(event.get("downloaded", 0)))
                            last_report = downloaded
                except queue.Empty:
                    pass

                elapsed = _format_elapsed(time.monotonic() - started_at)
                if last_report:
                    message = (
                        f"Скачиваем {profile.model_name}: получено "
                        f"{_format_bytes(last_report)}, прошло {elapsed}. "
                        "Это требуется только один раз."
                    )
                else:
                    message = (
                        f"Подключаемся для скачивания {profile.model_name} "
                        f"({profile.size_hint}) — прошло {elapsed}."
                    )
                progress("downloading_model", 20, message)
                process.join(timeout=0.5)

            if payload is None:
                try:
                    while True:
                        event = result_queue.get(timeout=2)
                        if event.get("event") == "result":
                            payload = event
                            break
                except queue.Empty as exc:
                    raise RuntimeError(
                        f"Процесс скачивания завершился без результата (код {process.exitcode})"
                    ) from exc
            if payload is None or not payload.get("ok"):
                error = payload.get("error") if payload else None
                raise RuntimeError(error or "Неизвестная ошибка скачивания модели")
            return Path(payload["path"])
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            result_queue.close()

    def _run_inference(
        self,
        request: TranscriptionRequest,
        audio_path: Path,
        model_path: Path,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        context = multiprocessing.get_context("spawn")
        engine = inference_engine()
        result_queue = context.Queue(maxsize=3)
        process = context.Process(
            target=_transcribe_in_child,
            args=(
                str(audio_path),
                str(model_path),
                request.language,
                request.initial_prompt,
                engine,
                result_queue,
            ),
            name=f"{engine}-whisper-inference",
        )
        process.start()
        started_at = time.monotonic()
        inference_started_at: float | None = None
        device_label: str | None = None
        payload: dict[str, Any] | None = None
        try:
            while process.is_alive():
                if self._cancelled(request):
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
                    raise TranscriptionCancelled("Транскрипция отменена")
                try:
                    event = result_queue.get_nowait()
                    if event.get("event") == "model_loaded":
                        inference_started_at = time.monotonic()
                        if event.get("device") == "cuda":
                            device_label = "GPU"
                        elif event.get("device") == "cpu":
                            device_label = "CPU"
                    elif event.get("event") == "result":
                        payload = event
                except queue.Empty:
                    pass
                if inference_started_at is None:
                    elapsed = _format_elapsed(time.monotonic() - started_at)
                    progress(
                        "loading_model",
                        30,
                        f"Загружаем {get_model_profile(request.model_profile).model_name} "
                        f"в память — прошло {elapsed}",
                    )
                else:
                    elapsed = _format_elapsed(time.monotonic() - inference_started_at)
                    device_note = f" на {device_label}" if device_label else ""
                    progress(
                        "transcribing",
                        40,
                        f"Распознаём речь локально{device_note} — прошло {elapsed}. "
                        "Длинные записи могут обрабатываться продолжительное время.",
                    )
                process.join(timeout=1)
            if payload is None:
                try:
                    while True:
                        event = result_queue.get(timeout=2)
                        if event.get("event") == "result":
                            payload = event
                            break
                except queue.Empty as exc:
                    raise RuntimeError(
                        f"Процесс распознавания завершился без результата (код {process.exitcode})"
                    ) from exc
            if payload is None:
                raise RuntimeError(
                    f"Процесс распознавания завершился без результата (код {process.exitcode})"
                )
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error") or "Неизвестная ошибка распознавания")
            return payload
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            result_queue.close()

    def transcribe(
        self, request: TranscriptionRequest, progress: ProgressCallback
    ) -> TranscriptionResult:
        profile = get_model_profile(request.model_profile)
        self._check_cancelled(request)
        progress("preparing", 10, "Подготавливаем аудиодорожку")
        try:
            audio_path = extract_audio(
                request.source,
                request.output_dir / "prepared-audio.wav",
                is_cancelled=lambda: self._cancelled(request),
            )
        except InterruptedError as exc:
            raise TranscriptionCancelled("Подготовка аудио отменена") from exc

        model_path = self._ensure_model(request, progress)
        self._check_cancelled(request)
        engine = inference_engine()
        package = "mlx_whisper" if engine == "mlx" else "faster_whisper"
        if importlib.util.find_spec(package) is None:
            display_name = "mlx-whisper" if engine == "mlx" else "faster-whisper"
            raise RuntimeError(
                f"{display_name} не установлен. Переустановите зависимости проекта."
            )
        raw_result = self._run_inference(request, audio_path, model_path, progress)
        text = raw_result["text"]
        detected_language = raw_result["language"]
        segments = raw_result["segments"]

        progress("exporting", 90, "Формируем файлы результата")
        self._check_cancelled(request)
        files = write_exports(
            output_dir=request.output_dir,
            original_name=request.original_name,
            model=model_repository(profile),
            language=str(detected_language) if detected_language else None,
            text=text,
            segments=segments,
        )
        audio_path.unlink(missing_ok=True)
        progress("completed", 100, "Транскрипция завершена")
        return TranscriptionResult(
            text=text,
            language=str(detected_language) if detected_language else None,
            segments=segments,
            files=files,
        )

