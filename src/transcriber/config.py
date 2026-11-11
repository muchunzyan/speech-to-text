from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from transcriber.models import default_model_cache_directory


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    offline: bool = False
    models_dir: Path = field(default_factory=default_model_cache_directory)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.getenv("TRANSCRIBER_HOST", "127.0.0.1"),
            port=int(os.getenv("TRANSCRIBER_PORT", "8000")),
            offline=_env_flag("TRANSCRIBER_OFFLINE"),
            models_dir=Path(
                os.getenv("TRANSCRIBER_MODELS_DIR", str(default_model_cache_directory()))
            ).expanduser(),
        )

