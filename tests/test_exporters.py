import json

from transcriber.exporters import normalize_segments, write_exports


def test_normalize_segments_skips_empty_text():
    result = normalize_segments(
        [
            {"start": 0, "end": 1.25, "text": " Привет "},
            {"start": 1.25, "end": 2, "text": "  "},
        ]
    )
    assert result == [{"start": 0.0, "end": 1.25, "text": "Привет"}]


def test_write_exports(tmp_path):
    files = write_exports(
        output_dir=tmp_path,
        original_name="meeting.mp4",
        model="test-model",
        language="ru",
        text="Привет, мир!",
        segments=[{"start": 0.0, "end": 1.5, "text": "Привет, мир!"}],
    )

    assert files["txt"].read_text(encoding="utf-8") == "Привет, мир!\n"
    assert "00:00:00,000 --> 00:00:01,500" in files["srt"].read_text(encoding="utf-8")
    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["source"] == "meeting.mp4"
    assert payload["text"] == "Привет, мир!"

