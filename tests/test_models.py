import pytest

from transcriber.models import (
    MODEL_PROFILES,
    DeviceCapabilities,
    choose_default_model_profile,
    inference_engine,
    model_profiles_public,
    model_repository,
    recommended_model_profile,
)


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


def test_default_model_uses_hardware_recommendation_when_nothing_is_downloaded():
    profiles = _profiles()
    profiles[0]["recommended"] = True
    assert choose_default_model_profile(profiles) == "fast"


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Darwin", "arm64", "mlx"),
        ("Windows", "AMD64", "ctranslate2"),
        ("Windows", "x86_64", "ctranslate2"),
    ],
)
def test_inference_engine_selects_platform_backend(system, machine, expected):
    assert inference_engine(system, machine) == expected


def test_inference_engine_rejects_unsupported_platform():
    with pytest.raises(RuntimeError, match="Поддерживаются"):
        inference_engine("Linux", "x86_64")


def test_model_profile_uses_backend_specific_weights():
    profile = MODEL_PROFILES["balanced"]
    assert model_repository(profile, "mlx") == "mlx-community/whisper-large-v3-turbo"
    assert (
        model_repository(profile, "ctranslate2")
        == "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    )


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        (DeviceCapabilities("Windows", 8), "fast"),
        (DeviceCapabilities("Windows", 16, "NVIDIA", 6, True), "balanced"),
        (DeviceCapabilities("Windows", 32, "NVIDIA", 12, True), "quality"),
        (DeviceCapabilities("Darwin", 8, "Apple Silicon", 8, True), "fast"),
        (DeviceCapabilities("Darwin", 16, "Apple Silicon", 16, True), "balanced"),
        (DeviceCapabilities("Darwin", 32, "Apple Silicon", 32, True), "quality"),
    ],
)
def test_recommended_model_matches_device_capacity(device, expected):
    engine = "mlx" if device.system == "Darwin" else "ctranslate2"
    assert recommended_model_profile(engine, device) == expected


def test_public_profiles_include_requirements_and_slow_device_warning(monkeypatch, tmp_path):
    monkeypatch.setattr("transcriber.models.find_cached_model", lambda *_: None)
    device = DeviceCapabilities("Windows", 8)

    profiles = model_profiles_public(tmp_path, device=device, engine="ctranslate2")

    assert profiles[0]["recommended"] is True
    assert "8 ГБ ОЗУ" in profiles[0]["requirements"]
    assert profiles[2]["suitability"] == "demanding"
    assert "очень медленно" in profiles[2]["suitability_message"]


def test_low_memory_device_warns_even_for_lightest_recommendation(monkeypatch, tmp_path):
    monkeypatch.setattr("transcriber.models.find_cached_model", lambda *_: None)

    profiles = model_profiles_public(
        tmp_path,
        device=DeviceCapabilities("Windows", 4),
        engine="ctranslate2",
    )

    assert profiles[0]["recommended"] is True
    assert profiles[0]["suitability"] == "demanding"
    assert "меньше 8 ГБ" in profiles[0]["suitability_message"]
