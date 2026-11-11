from __future__ import annotations

import argparse
import importlib.util
import platform
import sys

from transcriber.config import Settings
from transcriber.media import require_ffmpeg
from transcriber.models import MODEL_PROFILES, get_model_profile


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transcriber", description="Локальная транскрибация")
    subparsers = parser.add_subparsers(dest="command", required=True)

    web = subparsers.add_parser("web", help="Запустить локальный веб-интерфейс")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--offline", action="store_true", help="Запретить скачивание моделей")

    doctor = subparsers.add_parser("doctor", help="Проверить системные зависимости")
    doctor.set_defaults(command="doctor")

    models = subparsers.add_parser("models", help="Управление локальными моделями")
    models_subparsers = models.add_subparsers(dest="models_command", required=True)
    download = models_subparsers.add_parser("download", help="Скачать модель заранее")
    download.add_argument("profile", choices=MODEL_PROFILES, nargs="?", default="balanced")
    return parser


def _run_web(args: argparse.Namespace) -> None:
    import uvicorn

    from transcriber.web.app import create_app

    settings = Settings(host=args.host, port=args.port, offline=args.offline)
    app = create_app(settings=settings)
    print(f"Локальный интерфейс: http://{settings.host}:{settings.port}")
    uvicorn.run(app, host=settings.host, port=settings.port)


def _doctor() -> int:
    errors: list[str] = []
    try:
        require_ffmpeg()
        print("✓ FFmpeg и FFprobe найдены")
    except RuntimeError as exc:
        errors.append(str(exc))
        print(f"✗ {exc}")

    if sys.platform != "darwin" or platform.machine() != "arm64":
        errors.append("Для MLX требуется macOS на Apple Silicon")
        print("✗ Не удалось подтвердить совместимость с Apple Silicon")
    else:
        print("✓ macOS обнаружена")

    if importlib.util.find_spec("mlx_whisper") is None:
        errors.append("mlx-whisper не установлен")
        print("✗ mlx-whisper не установлен")
    else:
        try:
            import mlx_whisper  # noqa: F401

            print("✓ mlx-whisper установлен, Metal доступен")
        except ImportError as exc:
            errors.append(f"mlx-whisper установлен, но Metal недоступен: {exc}")
            print(f"✗ mlx-whisper установлен, но не может запустить Metal: {exc}")
    return 1 if errors else 0


def _download_model(profile_key: str) -> None:
    from huggingface_hub import snapshot_download

    profile = get_model_profile(profile_key)
    models_dir = Settings.from_env().models_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Скачиваем {profile.title}: {profile.repository}")
    path = snapshot_download(repo_id=profile.repository, cache_dir=models_dir)
    print(f"Модель сохранена: {path}")


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "web":
        _run_web(args)
    elif args.command == "doctor":
        raise SystemExit(_doctor())
    elif args.command == "models" and args.models_command == "download":
        _download_model(args.profile)

