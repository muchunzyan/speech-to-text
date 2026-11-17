from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from huggingface_hub import scan_cache_dir, snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError


@dataclass(frozen=True, slots=True)
class ModelProfile:
    key: str
    title: str
    model_name: str
    mlx_repository: str
    ctranslate2_repository: str
    description: str
    size_hint: str


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    system: str
    memory_gb: float
    gpu_name: str | None = None
    gpu_memory_gb: float | None = None
    gpu_acceleration: bool = False

    @property
    def summary(self) -> str:
        memory = f"{self.memory_gb:.0f} ГБ" if self.memory_gb else "объём памяти неизвестен"
        if self.system == "Darwin":
            return f"Apple Silicon · {memory} объединённой памяти · Metal"
        if self.gpu_name:
            video_memory = (
                f", {self.gpu_memory_gb:.0f} ГБ видеопамяти"
                if self.gpu_memory_gb
                else ""
            )
            return f"{memory} ОЗУ · {self.gpu_name}{video_memory}"
        return f"{memory} ОЗУ · GPU-ускорение не обнаружено, будет использоваться CPU"


MODEL_PROFILES: dict[str, ModelProfile] = {
    "fast": ModelProfile(
        key="fast",
        title="Быстро",
        model_name="Whisper Small",
        mlx_repository="mlx-community/whisper-small-mlx",
        ctranslate2_repository="Systran/faster-whisper-small",
        description="Меньше памяти и быстрее обработка; подходит для черновиков.",
        size_hint="~461 МБ",
    ),
    "balanced": ModelProfile(
        key="balanced",
        title="Сбалансированно",
        model_name="Whisper Large v3 Turbo",
        mlx_repository="mlx-community/whisper-large-v3-turbo",
        ctranslate2_repository="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        description="Рекомендуемый баланс скорости и качества для русской речи.",
        size_hint="~1,6 ГБ",
    ),
    "quality": ModelProfile(
        key="quality",
        title="Максимальное качество",
        model_name="Whisper Large v3",
        mlx_repository="mlx-community/whisper-large-v3-mlx",
        ctranslate2_repository="Systran/faster-whisper-large-v3",
        description="Наиболее точный, но более медленный и требовательный режим.",
        size_hint="~3,1 ГБ",
    ),
}


def inference_engine(system: str | None = None, machine: str | None = None) -> str:
    """Return the inference engine supported by the current platform."""
    current_system = system or platform.system()
    current_machine = (machine or platform.machine()).lower()
    if current_system == "Darwin" and current_machine in {"arm64", "aarch64"}:
        return "mlx"
    if current_system == "Windows" and current_machine in {"amd64", "x86_64"}:
        return "ctranslate2"
    raise RuntimeError(
        "Поддерживаются macOS на Apple Silicon и 64-битная Windows 10/11"
    )


def engine_title(engine: str) -> str:
    if engine == "mlx":
        return "MLX Whisper (Apple Metal)"
    if engine == "ctranslate2":
        return "Faster Whisper (CPU/CUDA)"
    raise ValueError(f"Неизвестный движок: {engine}")


def model_repository(profile: ModelProfile, engine: str | None = None) -> str:
    selected_engine = engine or inference_engine()
    if selected_engine == "mlx":
        return profile.mlx_repository
    if selected_engine == "ctranslate2":
        return profile.ctranslate2_repository
    raise ValueError(f"Неизвестный движок: {selected_engine}")


def _total_memory_gb(system: str) -> float:
    try:
        if system == "Windows":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.total_physical / 1024**3
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return page_size * pages / 1024**3
    except (AttributeError, OSError, ValueError):
        return 0.0


def _nvidia_gpu() -> tuple[str | None, float | None]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None, None
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        devices: list[tuple[str, float]] = []
        for line in result.stdout.splitlines():
            name, separator, memory_mb = line.rpartition(",")
            if separator:
                devices.append((name.strip(), float(memory_mb.strip())))
        if devices:
            name, memory_mb = max(devices, key=lambda device: device[1])
            return name, memory_mb / 1024
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None, None


@lru_cache(maxsize=1)
def detect_device_capabilities() -> DeviceCapabilities:
    system = platform.system()
    memory_gb = _total_memory_gb(system)
    if system == "Darwin":
        return DeviceCapabilities(
            system=system,
            memory_gb=memory_gb,
            gpu_name="Apple Silicon",
            gpu_memory_gb=memory_gb,
            gpu_acceleration=True,
        )

    gpu_name, gpu_memory_gb = _nvidia_gpu()
    gpu_acceleration = gpu_name is not None
    if not gpu_acceleration:
        try:
            import ctranslate2

            gpu_acceleration = ctranslate2.get_cuda_device_count() > 0
        except (ImportError, OSError, RuntimeError):
            pass
    return DeviceCapabilities(
        system=system,
        memory_gb=memory_gb,
        gpu_name=gpu_name,
        gpu_memory_gb=gpu_memory_gb,
        gpu_acceleration=gpu_acceleration,
    )


def recommended_model_profile(engine: str, device: DeviceCapabilities) -> str:
    if engine == "mlx":
        if device.memory_gb >= 24:
            return "quality"
        if device.memory_gb >= 12:
            return "balanced"
        return "fast"
    if device.gpu_memory_gb and device.gpu_memory_gb >= 10 and device.memory_gb >= 24:
        return "quality"
    if device.gpu_acceleration and device.memory_gb >= 12:
        return "balanced"
    return "fast"


def _requirements(profile_key: str, engine: str) -> str:
    if engine == "mlx":
        return {
            "fast": "Apple Silicon, от 8 ГБ объединённой памяти.",
            "balanced": "Apple Silicon, от 12 ГБ; рекомендуется 16 ГБ памяти.",
            "quality": "Apple Silicon, от 16 ГБ; рекомендуется 24 ГБ и больше.",
        }[profile_key]
    return {
        "fast": "От 8 ГБ ОЗУ; работает на CPU, отдельная видеокарта не обязательна.",
        "balanced": (
            "От 12 ГБ ОЗУ; рекомендуется NVIDIA GPU с 4–6 ГБ видеопамяти. "
            "На CPU будет заметно медленнее."
        ),
        "quality": (
            "От 16 ГБ ОЗУ; рекомендуется 24 ГБ ОЗУ и NVIDIA GPU с 10 ГБ "
            "видеопамяти. CPU-режим очень медленный."
        ),
    }[profile_key]


def _suitability(
    profile_key: str,
    recommended_key: str,
    engine: str,
    device: DeviceCapabilities,
) -> tuple[str, str]:
    recommended_title = MODEL_PROFILES[recommended_key].title
    if profile_key == recommended_key:
        if device.memory_gb and device.memory_gb < 8:
            return (
                "demanding",
                "Это самый щадящий режим, но обнаружено меньше 8 ГБ памяти. "
                "Обработка может быть медленной, а системе может потребоваться файл подкачки.",
            )
        return "recommended", "Лучший выбор для обнаруженных характеристик этого устройства."
    order = {"fast": 0, "balanced": 1, "quality": 2}
    if order[profile_key] > order[recommended_key]:
        reason = "недостаточно доступной памяти"
        if engine == "ctranslate2" and not device.gpu_acceleration:
            reason = "не обнаружено GPU-ускорение"
        return (
            "demanding",
            f"Может работать очень медленно: {reason}. "
            f"Рекомендуемый режим — «{recommended_title}».",
        )
    return (
        "supported",
        f"Подойдёт для более быстрой обработки. "
        f"Рекомендуемый режим — «{recommended_title}».",
    )


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


def model_profiles_public(
    cache_dir: Path,
    device: DeviceCapabilities | None = None,
    engine: str | None = None,
) -> list[dict[str, Any]]:
    selected_engine = engine or inference_engine()
    selected_device = device or detect_device_capabilities()
    recommended_key = recommended_model_profile(selected_engine, selected_device)
    return [
        {
            "key": profile.key,
            "title": profile.title,
            "model_name": profile.model_name,
            "repository": model_repository(profile, selected_engine),
            "engine": selected_engine,
            "engine_title": engine_title(selected_engine),
            "description": profile.description,
            "size_hint": profile.size_hint,
            "requirements": _requirements(profile.key, selected_engine),
            "recommended": profile.key == recommended_key,
            "suitability": _suitability(
                profile.key, recommended_key, selected_engine, selected_device
            )[0],
            "suitability_message": _suitability(
                profile.key, recommended_key, selected_engine, selected_device
            )[1],
            "downloaded": find_cached_model(
                model_repository(profile, selected_engine), cache_dir
            )
            is not None,
        }
        for profile in MODEL_PROFILES.values()
    ]


def choose_default_model_profile(profiles: list[dict[str, Any]]) -> str:
    downloaded = {str(profile["key"]) for profile in profiles if profile["downloaded"]}
    if "balanced" in downloaded:
        return "balanced"
    for profile in profiles:
        if profile["downloaded"]:
            return str(profile["key"])
    for profile in profiles:
        if profile.get("recommended"):
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

