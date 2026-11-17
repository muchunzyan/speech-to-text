import sys
from types import SimpleNamespace

from transcriber.transcription import (
    WHISPER_DECODING_OPTIONS,
    LocalWhisperTranscriber,
    TranscriptionRequest,
    _transcribe_with_faster_whisper,
)


def test_decoding_options_protect_against_repetition_loops():
    assert WHISPER_DECODING_OPTIONS["condition_on_previous_text"] is False
    assert WHISPER_DECODING_OPTIONS["compression_ratio_threshold"] == 2.0


def test_missing_model_reports_explicit_download_stage(monkeypatch, tmp_path):
    transcriber = LocalWhisperTranscriber()
    request = TranscriptionRequest(
        source=tmp_path / "source.wav",
        original_name="source.wav",
        output_dir=tmp_path / "result",
        model_profile="fast",
    )
    events = []

    monkeypatch.setattr("transcriber.transcription.find_cached_model", lambda *_: None)

    def fake_download_model(request, progress):
        assert request.model_profile == "fast"
        progress("downloading_model", 20, "Скачиваем тестовую модель")
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        return model_dir

    monkeypatch.setattr(transcriber, "_download_model", fake_download_model)

    path = transcriber._ensure_model(
        request,
        lambda stage, percent, message: events.append((stage, percent, message)),
    )

    assert path == tmp_path / "model"
    assert events[0][0] == "downloading_model"
    assert "только один раз" in events[0][2]
    assert events[-1][0] == "loading_model"


def test_faster_whisper_falls_back_to_cpu_when_cuda_cannot_load(monkeypatch):
    devices = []

    class FakeModel:
        def __init__(self, _model_path, device, compute_type):
            devices.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("CUDA libraries are missing")

        def transcribe(self, _audio_path, **_kwargs):
            segments = [SimpleNamespace(start=0.0, end=1.0, text=" Тест")]
            return iter(segments), SimpleNamespace(language="ru")

    events = []
    monkeypatch.setitem(
        sys.modules,
        "ctranslate2",
        SimpleNamespace(get_cuda_device_count=lambda: 1),
    )
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeModel),
    )

    result = _transcribe_with_faster_whisper(
        "audio.wav", "model", "ru", None, SimpleNamespace(put=events.append)
    )

    assert devices == [("cuda", "float16"), ("cpu", "int8")]
    assert events[-1]["device"] == "cpu"
    assert result["text"] == "Тест"

