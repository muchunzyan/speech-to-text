from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _timestamp(seconds: float, decimal: str = ",") -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal}{millis:03d}"


def normalize_segments(raw_segments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for raw in raw_segments or []:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(raw.get("start", 0.0)),
                "end": float(raw.get("end", raw.get("start", 0.0))),
                "text": text,
            }
        )
    return segments


def write_exports(
    output_dir: Path,
    original_name: str,
    model: str,
    language: str | None,
    text: str,
    segments: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_text = text.strip()

    txt_path = output_dir / "transcript.txt"
    md_path = output_dir / "transcript.md"
    json_path = output_dir / "transcript.json"
    srt_path = output_dir / "transcript.srt"

    txt_path.write_text(f"{clean_text}\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Транскрипт",
                "",
                f"- Исходный файл: `{original_name}`",
                f"- Язык: `{language or 'auto'}`",
                f"- Модель: `{model}`",
                "",
                clean_text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    payload = {
        "source": original_name,
        "model": model,
        "language": language,
        "created_at": datetime.now(UTC).isoformat(),
        "text": clean_text,
        "segments": segments,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    srt_blocks = []
    for index, segment in enumerate(segments, start=1):
        srt_blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_timestamp(segment['start'])} --> {_timestamp(segment['end'])}",
                    segment["text"],
                ]
            )
        )
    srt_path.write_text("\n\n".join(srt_blocks) + ("\n" if srt_blocks else ""), encoding="utf-8")
    return {"txt": txt_path, "md": md_path, "json": json_path, "srt": srt_path}

