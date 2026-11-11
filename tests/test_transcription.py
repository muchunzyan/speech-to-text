from transcriber.transcription import (
    WHISPER_DECODING_OPTIONS,
    LocalWhisperTranscriber,
    TranscriptionRequest,
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

