import time
from pathlib import Path

from transcriber.jobs import JobManager
from transcriber.transcription import TranscriptionResult


class FakeTranscriber:
    def transcribe(self, request, progress):
        progress("transcribing", 50, "Тест")
        result_file = request.output_dir / "transcript.txt"
        result_file.parent.mkdir(parents=True)
        result_file.write_text("готово", encoding="utf-8")
        return TranscriptionResult(
            text="готово", language="ru", segments=[], files={"txt": result_file}
        )


def test_job_manager_processes_one_job():
    manager = JobManager(transcriber=FakeTranscriber())
    manager.start()
    try:
        job = manager.reserve("sample.wav", "fast", "ru", None, True)
        Path(job.input_path).write_bytes(b"audio")
        manager.enqueue(job.id)
        deadline = time.monotonic() + 2
        while job.status not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.01)
        assert job.status == "completed"
        assert job.text == "готово"
        assert job.public()["elapsed_seconds"] is not None
        assert job.public()["downloads"]["txt"].endswith("/download/txt")
    finally:
        manager.stop()


def test_queued_job_can_be_cancelled():
    manager = JobManager(transcriber=FakeTranscriber())
    try:
        job = manager.reserve("sample.wav", "fast", "ru", None, True)
        Path(job.input_path).write_bytes(b"audio")
        manager.enqueue(job.id)

        cancelled = manager.cancel(job.id)

        assert cancelled is job
        assert job.status == "cancelled"
        assert job.public()["can_cancel"] is False
    finally:
        manager.stop()

