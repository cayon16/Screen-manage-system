import pytest
from pydantic import ValidationError

from app.superdoc.settings import (
    AiSettings,
    InternalSettings,
    PublicSettings,
    load_settings,
    save_settings,
    settings_from_env,
)


def test_defaults_are_demo_mode_with_a_sane_timeout():
    s = AiSettings()
    assert s.mode == "demo"
    assert s.public.provider == "gemini"
    assert s.internal.protocol == "bridge"
    assert s.timeout_sec == 30
    assert s.system_prompt is None


def test_unknown_fields_are_rejected():
    # extra="forbid": mot truong la (vd "api_key") khong duoc phep lot vao cau hinh.
    with pytest.raises(ValidationError):
        AiSettings.model_validate({"mode": "demo", "api_key": "khoa-gia"})
    with pytest.raises(ValidationError):
        PublicSettings.model_validate({"provider": "gemini", "api_key": "khoa-gia"})


@pytest.mark.parametrize("value", [4, 61, 0, -1])
def test_timeout_outside_5_to_60_seconds_is_rejected(value):
    with pytest.raises(ValidationError):
        AiSettings(timeout_sec=value)


def test_base_url_is_normalised_and_validated():
    assert InternalSettings(base_url="  http://10.0.0.20:9000/  ").base_url == "http://10.0.0.20:9000"
    assert InternalSettings(base_url="").base_url is None
    assert PublicSettings(provider="openai", base_url="https://api.example.com/v1/").base_url == "https://api.example.com/v1"
    with pytest.raises(ValidationError):
        InternalSettings(base_url="10.0.0.20:9000")
    with pytest.raises(ValidationError):
        PublicSettings(base_url="ftp://x")


def test_unknown_mode_or_provider_is_rejected():
    with pytest.raises(ValidationError):
        AiSettings(mode="bat-ky")
    with pytest.raises(ValidationError):
        PublicSettings(provider="khong-co")


# ---------- khoi dau tu bien moi truong (tuong thich ban cu) ----------


def test_env_without_anything_means_demo():
    assert settings_from_env({}).mode == "demo"
    assert settings_from_env({"SUPERDOC_PROVIDER": "mock"}).mode == "demo"


def test_old_env_gemini_maps_to_public_gemini():
    s = settings_from_env({"SUPERDOC_PROVIDER": "gemini", "GEMINI_MODEL": "gemini-x"})
    assert (s.mode, s.public.provider, s.public.model) == ("public", "gemini", "gemini-x")


def test_env_can_choose_the_other_public_providers_and_their_models():
    s = settings_from_env({"SUPERDOC_PROVIDER": "openai", "OPENAI_MODEL": "gpt-test"})
    assert (s.mode, s.public.provider, s.public.model) == ("public", "openai", "gpt-test")
    s = settings_from_env({"SUPERDOC_PROVIDER": "anthropic", "ANTHROPIC_MODEL": "claude-test"})
    assert (s.mode, s.public.provider, s.public.model) == ("public", "anthropic", "claude-test")


def test_env_internal_url_is_picked_up():
    s = settings_from_env({"SUPERDOC_INTERNAL_URL": "http://10.0.0.20:9000/"})
    assert s.internal.base_url == "http://10.0.0.20:9000"


def test_bad_env_url_falls_back_to_demo_instead_of_crashing():
    s = settings_from_env({"SUPERDOC_PROVIDER": "gemini", "SUPERDOC_INTERNAL_URL": "khong-phai-url"})
    assert s.mode == "demo"


# ---------- file ----------


def test_save_then_load_round_trips_including_vietnamese(tmp_path):
    path = tmp_path / "ai_settings.json"
    original = AiSettings(
        mode="internal",
        internal=InternalSettings(base_url="http://10.0.0.20:9000"),
        system_prompt="Bạn là Superdoc — trợ lý ảo.",
    )
    save_settings(path, original)
    assert "trợ lý ảo" in path.read_text(encoding="utf-8")  # khong bi escape thanh \uXXXX
    assert load_settings(path, {}) == original
    assert not (tmp_path / "ai_settings.json.tmp").exists()


def test_file_wins_over_environment(tmp_path):
    path = tmp_path / "ai_settings.json"
    save_settings(path, AiSettings(mode="demo"))
    assert load_settings(path, {"SUPERDOC_PROVIDER": "gemini"}).mode == "demo"


def test_missing_file_uses_environment(tmp_path):
    assert load_settings(tmp_path / "chua-co.json", {"SUPERDOC_PROVIDER": "gemini"}).mode == "public"
    assert load_settings(None, {}).mode == "demo"


def test_corrupt_file_falls_back_to_environment(tmp_path):
    path = tmp_path / "ai_settings.json"
    path.write_text("{ day khong phai json", encoding="utf-8")
    assert load_settings(path, {"SUPERDOC_PROVIDER": "openai"}).public.provider == "openai"
    path.write_text('{"mode": "bat-ky"}', encoding="utf-8")
    assert load_settings(path, {}).mode == "demo"


def test_saved_file_never_contains_an_api_key(tmp_path, monkeypatch):
    # Dat key gia trong moi truong roi luu: file ra khong duoc co chuoi nay o dau ca.
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SUPERDOC_INTERNAL_TOKEN"):
        monkeypatch.setenv(name, "KHOA-BI-MAT-12345")
    path = tmp_path / "ai_settings.json"
    save_settings(path, settings_from_env({"SUPERDOC_PROVIDER": "gemini"}))
    assert "KHOA-BI-MAT" not in path.read_text(encoding="utf-8")
