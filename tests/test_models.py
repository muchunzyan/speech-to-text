from transcriber.models import choose_default_model_profile


def _profiles(*downloaded):
    return [
        {"key": "fast", "downloaded": "fast" in downloaded},
        {"key": "balanced", "downloaded": "balanced" in downloaded},
        {"key": "quality", "downloaded": "quality" in downloaded},
    ]


def test_default_model_prefers_downloaded_balanced_profile():
    assert choose_default_model_profile(_profiles("balanced", "quality")) == "balanced"


def test_default_model_uses_only_downloaded_profile():
    assert choose_default_model_profile(_profiles("quality")) == "quality"


def test_default_model_falls_back_to_balanced():
    assert choose_default_model_profile(_profiles()) == "balanced"
