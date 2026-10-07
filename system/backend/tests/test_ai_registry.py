import pytest

from app.superdoc import registry
from app.superdoc.anthropic_provider import AnthropicProvider
from app.superdoc.bridge_provider import BridgeProvider
from app.superdoc.gemini_provider import GeminiSuperdocProvider
from app.superdoc.mock_provider import MockSuperdocProvider
from app.superdoc.openai_provider import OpenAIProvider
from app.superdoc.registry import ProviderConfigError, build, describe, problems
from app.superdoc.settings import AiSettings, InternalSettings, PublicSettings


def _public(provider="gemini", model=None, base_url=None, **kwargs) -> AiSettings:
    return AiSettings(mode="public", public=PublicSettings(provider=provider, model=model, base_url=base_url), **kwargs)


def _internal(protocol="bridge", base_url="http://10.0.0.20:9000", model=None) -> AiSettings:
    return AiSettings(mode="internal", internal=InternalSettings(protocol=protocol, base_url=base_url, model=model))


def _fields(settings, env) -> list[str]:
    return [p.field for p in problems(settings, env)]


# ---------- do day du theo che do ----------


def test_demo_needs_nothing():
    assert problems(AiSettings(), {}) == []
    assert isinstance(build(AiSettings(), {}), MockSuperdocProvider)


def test_only_the_selected_mode_is_checked():
    # Cau hinh `internal` dang do khong duoc lam hong che do `demo` dang chay.
    half_done = AiSettings(mode="demo", internal=InternalSettings(protocol="openai_compatible"))
    assert problems(half_done, {}) == []


@pytest.mark.parametrize(
    ("provider", "key_env"),
    [("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")],
)
def test_public_provider_requires_its_own_key_in_the_environment(provider, key_env):
    settings = _public(provider, model="m")
    assert f"secrets.{key_env}" in _fields(settings, {})
    assert f"secrets.{key_env}" not in _fields(settings, {key_env: "khoa-gia"})
    # Khoa cua nha cung cap khac khong thay the duoc.
    other = "OPENAI_API_KEY" if key_env != "OPENAI_API_KEY" else "GEMINI_API_KEY"
    assert f"secrets.{key_env}" in _fields(settings, {other: "khoa-gia"})


def test_a_blank_key_counts_as_missing():
    assert "secrets.GEMINI_API_KEY" in _fields(_public("gemini"), {"GEMINI_API_KEY": "   "})


def test_openai_has_no_default_model_but_the_others_do():
    env = {"OPENAI_API_KEY": "k", "GEMINI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"}
    assert _fields(_public("openai"), env) == ["public.model"]
    assert _fields(_public("gemini"), env) == []
    assert _fields(_public("anthropic"), env) == []


def test_model_can_come_from_the_settings_or_the_environment():
    env = {"OPENAI_API_KEY": "k"}
    assert _fields(_public("openai", model="gpt-test"), env) == []
    assert _fields(_public("openai"), {**env, "OPENAI_MODEL": "gpt-env"}) == []


def test_internal_requires_an_address_and_openai_compatible_also_a_model():
    assert _fields(_internal(base_url=None), {}) == ["internal.base_url"]
    assert _fields(_internal("bridge"), {}) == []
    assert _fields(_internal("openai_compatible", model=None), {}) == ["internal.model"]
    assert _fields(_internal("openai_compatible", model="llama"), {}) == []
    # Token cua chatbot noi bo la tuy chon.
    assert _fields(_internal("bridge"), {}) == []


def test_build_raises_the_first_problem_with_a_message_for_the_operator():
    with pytest.raises(ProviderConfigError) as info:
        build(_public("openai"), {})
    assert info.value.field == "secrets.OPENAI_API_KEY"
    assert "OPENAI_API_KEY" in info.value.message


# ---------- dung dung provider ----------


def test_build_gemini_with_default_and_custom_model():
    provider = build(_public("gemini"), {"GEMINI_API_KEY": "k"})
    assert isinstance(provider, GeminiSuperdocProvider)
    assert provider.model == "gemini-2.5-flash"
    assert build(_public("gemini", model="gemini-x"), {"GEMINI_API_KEY": "k"}).model == "gemini-x"


def test_build_anthropic():
    provider = build(_public("anthropic"), {"ANTHROPIC_API_KEY": "k"})
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == registry.ANTHROPIC_DEFAULT_MODEL


def test_build_openai_uses_the_public_endpoint_unless_overridden():
    provider = build(_public("openai", model="gpt-test"), {"OPENAI_API_KEY": "k"})
    assert isinstance(provider, OpenAIProvider)
    assert (provider.name, provider.model) == ("openai", "gpt-test")
    assert provider._url == "https://api.openai.com/v1/chat/completions"

    custom = build(_public("openai", model="m", base_url="https://gateway.example.com/v1"), {"OPENAI_API_KEY": "k"})
    assert custom._url == "https://gateway.example.com/v1/chat/completions"


def test_build_internal_bridge_passes_the_optional_token():
    provider = build(_internal("bridge"), {"SUPERDOC_INTERNAL_TOKEN": "tok"})
    assert isinstance(provider, BridgeProvider)
    assert provider._client.headers["authorization"] == "Bearer tok"
    assert "authorization" not in build(_internal("bridge"), {})._client.headers


def test_build_internal_openai_compatible_is_labelled_as_such():
    provider = build(_internal("openai_compatible", model="llama"), {})
    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai_compatible"
    assert provider._url == "http://10.0.0.20:9000/chat/completions"


async def test_build_passes_the_configured_timeout_to_the_http_client():
    provider = build(_public("anthropic", timeout_sec=12), {"ANTHROPIC_API_KEY": "k"})
    assert provider._client.timeout.read == 12
    await provider.aclose()


# ---------- mo ta ----------


def test_describe_never_includes_a_secret_and_resolves_the_model():
    env = {"OPENAI_API_KEY": "KHOA-BI-MAT"}
    info = describe(_public("openai", model="gpt-test"), env)
    assert info == {"mode": "public", "provider": "openai", "model": "gpt-test",
                    "base_url": "https://api.openai.com/v1"}
    assert "KHOA-BI-MAT" not in str(info)
    assert describe(AiSettings(), {}) == {"mode": "demo", "provider": "mock", "model": None, "base_url": None}
    assert describe(_internal("bridge"), {})["base_url"] == "http://10.0.0.20:9000"
    assert describe(_public("gemini"), {})["model"] == "gemini-2.5-flash"


def test_catalog_lists_every_choice_the_registry_can_build():
    assert {(c["mode"], c["provider"]) for c in registry.CATALOG} == {
        ("demo", "mock"), ("internal", "bridge"), ("internal", "openai_compatible"),
        ("public", "gemini"), ("public", "openai"), ("public", "anthropic"),
    }
    assert next(c for c in registry.CATALOG if c["provider"] == "openai")["model_required"] is True
