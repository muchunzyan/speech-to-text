from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from transcriber.models import default_model_cache_directory
from transcriber.transcription import (
    LocalWhisperTranscriber,
    TranscriptionCancelled,
    TranscriptionRequest,
    TranscriptionResult,
)


class Transcriber(Protocol):
    def transcribe(self, request: TranscriptionRequest, progress: Any) -> TranscriptionResult: ...


@dataclass(slots=True)
class Job:
    id: str
    original_name: str
    input_path: Path
    output_dir: Path
    model_profile: str
    language: str | None
    initial_prompt: str | None
    offline: bool
    model_cache_dir: Path
    status: str = "uploading"
    stage: str = "uploading"
    progress: int = 0
    message: str = "Загружаем файл"
    text: str | None = None
    detected_language: str | None = None
    error: str | None = None
    result_files: dict[str, Path] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    started_monotonic: float | None = field(default=None, repr=False)
    finished_monotonic: float | None = field(default=None, repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def public(self) -> dict[str, Any]:
        downloads = {
            kind: f"/api/jobs/{self.id}/download/{kind}" for kind in self.result_files
        }
        elapsed_seconds = None
        if self.started_monotonic is not None and self.finished_monotonic is not None:
            elapsed_seconds = round(self.finished_monotonic - self.started_monotonic, 1)
        return {
            "id": self.id,
            "original_name": self.original_name,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "text": self.text,
            "language": self.detected_language,
            "error": self.error,
            "downloads": downloads,
            "can_cancel": self.status in {"queued", "processing", "cancelling"},
            "indeterminate": self.stage in {
                "downloading_model",
                "loading_model",
                "transcribing",
                "cancelling",
            },
            "elapsed_seconds": elapsed_seconds,
            "created_at": self.created_at,
        }


class JobManager:
    def __init__(
        self,
        transcriber: Transcriber | None = None,
        models_dir: Path | None = None,
    ) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="local-transcriber-"))
        self.models_dir = models_dir or default_model_cache_directory()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._transcriber = transcriber or LocalWhisperTranscriber()
        self._jobs: dict[str, Job] = {}
        self._jobs_lock = threading.RLock()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._worker, name="transcription-worker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        with self._jobs_lock:
            for job in self._jobs.values():
                if job.status in {"queued", "processing", "cancelling"}:
                    job.cancel_event.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)
        if not self._thread or not self._thread.is_alive():
            shutil.rmtree(self.root, ignore_errors=True)

    def reserve(
        self,
        original_name: str,
        model_profile: str,
        language: str | None,
        initial_prompt: str | None,
        offline: bool,
    ) -> Job:
        job_id = uuid.uuid4().hex
        job_dir = self.root / job_id
        job_dir.mkdir(parents=True)
        safe_suffix = Path(original_name).suffix.lower()
        input_path = job_dir / f"input{safe_suffix}"
        job = Job(
            id=job_id,
            original_name=original_name,
            input_path=input_path,
            output_dir=job_dir / "results",
            model_profile=model_profile,
            language=language,
            initial_prompt=initial_prompt,
            offline=offline,
            model_cache_dir=self.models_dir,
        )
        with self._jobs_lock:
            self._jobs[job_id] = job
        return job

    def enqueue(self, job_id: str) -> None:
        with self._jobs_lock:
            job = self._jobs[job_id]
            job.status = "queued"
            job.stage = "queued"
            job.progress = 5
            job.message = "Задание добавлено в очередь"
        self._queue.put(job_id)

    def fail_upload(self, job_id: str, message: str) -> None:
        with self._jobs_lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.stage = "failed"
            job.message = "Не удалось загрузить файл"
            job.error = message

    def cancel(self, job_id: str) -> Job | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in {"completed", "failed", "cancelled"}:
                return job
            job.cancel_event.set()
            if job.status in {"uploading", "queued"}:
                job.status = "cancelled"
                job.stage = "cancelled"
                job.message = "Задание отменено"
            else:
                job.status = "cancelling"
                job.stage = "cancelling"
                job.message = "Останавливаем обработку…"
            return job

    def get(self, job_id: str) -> Job | None:
        with self._jobs_lock:
            return self._jobs.get(job_id)

    def is_model_active(self, model_profile: str) -> bool:
        with self._jobs_lock:
            return any(
                job.model_profile == model_profile
                and job.status in {"queued", "processing", "cancelling"}
                for job in self._jobs.values()
            )

    def _update(self, job_id: str, stage: str, progress: int, message: str) -> None:
        with self._jobs_lock:
            job = self._jobs[job_id]
            if job.cancel_event.is_set():
                return
            job.stage = stage
            job.progress = max(0, min(progress, 100))
            job.message = message

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                self._queue.task_done()
                return
            job = self.get(job_id)
            if job is None:
                self._queue.task_done()
                continue
            if job.cancel_event.is_set():
                job.input_path.unlink(missing_ok=True)
                self._queue.task_done()
                continue
            try:
                with self._jobs_lock:
                    job.status = "processing"
                    job.started_monotonic = time.monotonic()
                request = TranscriptionRequest(
                    source=job.input_path,
                    original_name=job.original_name,
                    output_dir=job.output_dir,
                    model_profile=job.model_profile,
                    language=job.language,
                    initial_prompt=job.initial_prompt,
                    offline=job.offline,
                    is_cancelled=job.cancel_event.is_set,
                    model_cache_dir=job.model_cache_dir,
                )
                result = self._transcriber.transcribe(
                    request,
                    lambda stage, percent, message, jid=job_id: self._update(
                        jid, stage, percent, message
                    ),
                )
                with self._jobs_lock:
                    job.finished_monotonic = time.monotonic()
                    job.status = "completed"
                    job.stage = "completed"
                    job.progress = 100
                    job.message = "Транскрипция завершена"
                    job.text = result.text
                    job.detected_language = result.language
                    job.result_files = result.files
                job.input_path.unlink(missing_ok=True)
            except TranscriptionCancelled:
                with self._jobs_lock:
                    job.finished_monotonic = time.monotonic()
                    job.status = "cancelled"
                    job.stage = "cancelled"
                    job.message = "Задание отменено"
                    job.error = None
                job.input_path.unlink(missing_ok=True)
            except Exception as exc:  # worker boundary: expose a useful message to the local UI
                with self._jobs_lock:
                    job.finished_monotonic = time.monotonic()
                    job.status = "failed"
                    job.stage = "failed"
                    job.message = "Транскрипция завершилась с ошибкой"
                    job.error = str(exc)
            finally:
                self._queue.task_done()

