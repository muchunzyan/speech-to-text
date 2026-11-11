from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from transcriber.config import Settings
from transcriber.jobs import JobManager
from transcriber.models import (
    choose_default_model_profile,
    delete_cached_model,
    get_model_profile,
    model_profiles_public,
)

SUPPORTED_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".avi",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


def create_app(settings: Settings | None = None, manager: JobManager | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    manager = manager or JobManager(models_dir=settings.models_dir)
    models_dir = manager.models_dir
    web_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=web_dir / "templates")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        manager.start()
        yield
        manager.stop()

    app = FastAPI(title="Локальный транскрайбер", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.job_manager = manager
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        profiles = model_profiles_public(models_dir)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "profiles": profiles,
                "default_profile": choose_default_model_profile(profiles),
                "offline": settings.offline,
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/models")
    async def models() -> dict:
        return {
            "models": model_profiles_public(models_dir),
            "cache_directory": str(models_dir),
        }

    @app.delete("/api/models/{profile_key}")
    async def delete_model(profile_key: str) -> dict:
        try:
            profile = get_model_profile(profile_key)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        if manager.is_model_active(profile_key):
            raise HTTPException(409, "Нельзя удалить модель, пока она используется заданием")
        deleted = delete_cached_model(profile.repository, models_dir)
        return {"deleted": deleted, "profile": profile_key}

    @app.post("/api/jobs", status_code=202)
    async def create_job(
        file: Annotated[UploadFile, File()],
        model_profile: Annotated[str, Form()] = "balanced",
        language: Annotated[str, Form()] = "ru",
        initial_prompt: Annotated[str, Form()] = "",
    ) -> dict:
        original_name = Path(file.filename or "media").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(415, f"Неподдерживаемый формат. Допустимы: {allowed}")
        try:
            get_model_profile(model_profile)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        selected_language = None if language == "auto" else language.strip() or None
        prompt = initial_prompt.strip() or None
        job = manager.reserve(
            original_name=original_name,
            model_profile=model_profile,
            language=selected_language,
            initial_prompt=prompt,
            offline=settings.offline,
        )
        try:
            with job.input_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    destination.write(chunk)
        except Exception as exc:
            manager.fail_upload(job.id, str(exc))
            raise HTTPException(500, "Не удалось сохранить загруженный файл") from exc
        finally:
            await file.close()
        manager.enqueue(job.id)
        return job.public()

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str) -> dict:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(404, "Задание не найдено")
        return job.public()

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict:
        job = manager.cancel(job_id)
        if job is None:
            raise HTTPException(404, "Задание не найдено")
        return job.public()

    @app.get("/api/jobs/{job_id}/download/{kind}")
    async def download(job_id: str, kind: str) -> FileResponse:
        job = manager.get(job_id)
        if job is None or job.status != "completed":
            raise HTTPException(404, "Результат не найден")
        path = job.result_files.get(kind)
        if path is None or not path.is_file():
            raise HTTPException(404, "Формат результата не найден")
        return FileResponse(path, filename=f"transcript.{kind}")

    return app

