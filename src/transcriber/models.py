from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import scan_cache_dir, snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError


@dataclass(frozen=True, slots=True)
class ModelProfile:
    key: str
    title: str
    model_name: str
    repository: str
    description: str
    size_hint: str


MODEL_PROFILES: dict[str, ModelProfile] = {
    "fast": ModelProfile(
        key="fast",
        title="Быстро",
        model_name="Whisper Small",
        repository="mlx-community/whisper-small-mlx",
        description="Меньше памяти и быстрее обработка; подходит для черновиков.",
        size_hint="~461 МБ",
    ),
    "balanced": ModelProfile(
        key="balanced",
        title="Сбалансированно",
        model_name="Whisper Large v3 Turbo",
        repository="mlx-community/whisper-large-v3-turbo",
        description="Рекомендуемый баланс скорости и качества для русской речи.",
        size_hint="~1,6 ГБ",
    ),
    "quality": ModelProfile(
        key="quality",
        title="Максимальное качество",
        model_name="Whisper Large v3",
        repository="mlx-community/whisper-large-v3-mlx",
        description="Наиболее точный, но более медленный и требовательный режим.",
        size_hint="~3,1 ГБ",
    ),
}


def get_model_profile(key: str) -> ModelProfile:
    try:
        return MODEL_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Неизвестный профиль модели: {key}") from exc


def default_model_cache_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "models"


def find_cached_model(repository: str, cache_dir: Path) -> Path | None:
    """Return a complete local snapshot path without making a network request."""
    try:
        return Path(
            snapshot_download(
                repo_id=repository,
                cache_dir=cache_dir,
                local_files_only=True,
            )
        )
    except LocalEntryNotFoundError:
        return None


def model_profiles_public(cache_dir: Path) -> list[dict[str, str | bool]]:
    return [
        {
            "key": profile.key,
            "title": profile.title,
            "model_name": profile.model_name,
            "repository": profile.repository,
            "description": profile.description,
            "size_hint": profile.size_hint,
            "downloaded": find_cached_model(profile.repository, cache_dir) is not None,
        }
        for profile in MODEL_PROFILES.values()
    ]


def choose_default_model_profile(profiles: list[dict[str, str | bool]]) -> str:
    downloaded = {str(profile["key"]) for profile in profiles if profile["downloaded"]}
    if "balanced" in downloaded:
        return "balanced"
    for profile in profiles:
        if profile["downloaded"]:
            return str(profile["key"])
    return "balanced"


def delete_cached_model(repository: str, cache_dir: Path) -> bool:
    """Delete one managed model repository from the application's cache."""
    cache_root = cache_dir.resolve()
    repository_dir = (cache_root / f"models--{repository.replace('/', '--')}").resolve()
    lock_dir = (cache_root / ".locks" / repository_dir.name).resolve()
    if repository_dir.parent != cache_root:
        raise ValueError("Некорректный путь модели")

    existed = False
    try:
        cache_info = scan_cache_dir(cache_root)
        cached_repo = next((repo for repo in cache_info.repos if repo.repo_id == repository), None)
        if cached_repo is not None:
            revisions = [revision.commit_hash for revision in cached_repo.revisions]
            if revisions:
                cache_info.delete_revisions(*revisions).execute()
                existed = True
    except (FileNotFoundError, OSError):
        pass

    # Also remove an incomplete download that is not yet visible to scan_cache_dir().
    if repository_dir.exists():
        shutil.rmtree(repository_dir)
        existed = True
    if lock_dir.parent == cache_root / ".locks" and lock_dir.exists():
        shutil.rmtree(lock_dir)
    return existed

