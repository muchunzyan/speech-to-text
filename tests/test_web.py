import time

from fastapi.testclient import TestClient

from transcriber.config import Settings
from transcriber.jobs import JobManager
from transcriber.transcription import TranscriptionResult
from transcriber.web.app import create_app


class FakeTranscriber:
    def transcribe(self, request, progress):
        progress("transcribing", 50, "Тестовое распознавание")
        result_file = request.output_dir / "transcript.txt"
        result_file.parent.mkdir(parents=True)
        result_file.write_text("локальный результат", encoding="utf-8")
        return TranscriptionResult(
            text="локальный результат",
            language="ru",
            segments=[],
            files={"txt": result_file},
        )


def test_web_upload_and_result(tmp_path):
    models_dir = tmp_path / "models"
    manager = JobManager(transcriber=FakeTranscriber(), models_dir=models_dir)
    app = create_app(Settings(offline=True, models_dir=models_dir), manager=manager)

    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Локальный транскрайбер" in page.text
        assert "Помогает точнее распознавать имена" in page.text
        assert "Whisper Large v3 Turbo" in page.text

        models = client.get("/api/models")
        assert models.status_code == 200
        assert len(models.json()["models"]) == 3
        assert models.json()["cache_directory"] == str(models_dir)

        response = client.post(
            "/api/jobs",
            files={"file": ("sample.wav", b"fake audio", "audio/wav")},
            data={"model_profile": "fast", "language": "ru"},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]

        deadline = time.monotonic() + 2
        payload = response.json()
        while payload["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
            payload = client.get(f"/api/jobs/{job_id}").json()
            time.sleep(0.01)

        assert payload["status"] == "completed"
        assert payload["text"] == "локальный результат"
        assert payload["elapsed_seconds"] is not None
        download = client.get(payload["downloads"]["txt"])
        assert download.text == "локальный результат"


def test_web_rejects_unsupported_extension(tmp_path):
    models_dir = tmp_path / "models"
    manager = JobManager(transcriber=FakeTranscriber(), models_dir=models_dir)
    app = create_app(Settings(models_dir=models_dir), manager=manager)
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            files={"file": ("notes.txt", b"text", "text/plain")},
        )
        assert response.status_code == 415


def test_web_deletes_managed_model(tmp_path):
    models_dir = tmp_path / "models"
    repository_dir = models_dir / "models--mlx-community--whisper-small-mlx"
    repository_dir.mkdir(parents=True)
    (repository_dir / "weights.npz").write_bytes(b"model")
    manager = JobManager(transcriber=FakeTranscriber(), models_dir=models_dir)
    app = create_app(Settings(models_dir=models_dir), manager=manager)

    with TestClient(app) as client:
        response = client.delete("/api/models/fast")

        assert response.status_code == 200
        assert response.json()["deleted"] is True
        assert not repository_dir.exists()

