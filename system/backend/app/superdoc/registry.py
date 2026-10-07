"""Bang tra: cau hinh AI nao can nhung gi, va dung provider tuong ung.

Them nha cung cap moi = them 1 file provider + them 1 nhanh o problems()/build()/describe() +
1 dong o CATALOG. Khong cho nao khac trong he thong phai biet ten nha cung cap.
"""

from __future__ import annotations

import os
from typing import Mapping

from app.config import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_DEFAULT_MODEL,
    GEMINI_API_KEY_ENV,
    GEMINI_DEFAULT_MODEL,
    INTERNAL_TOKEN_ENV,
    OPENAI_API_KEY_ENV,
)
from app.superdoc.anthropic_provider import AnthropicProvider
from app.superdoc.base import SuperdocProvider
from app.superdoc.bridge_provider import BridgeProvider
from app.superdoc.gemini_provider import GeminiSuperdocProvider
from app.superdoc.mock_provider import MockSuperdocProvider
from app.superdoc.openai_provider import DEFAULT_BASE_URL as OPENAI_DEFAULT_BASE_URL
from app.superdoc.openai_provider import OpenAIProvider
from app.superdoc.settings import AiSettings

SECRET_ENV_NAMES = (GEMINI_API_KEY_ENV, OPENAI_API_KEY_ENV, ANTHROPIC_API_KEY_ENV, INTERNAL_TOKEN_ENV)

_KEY_ENV = {"gemini": GEMINI_API_KEY_ENV, "openai": OPENAI_API_KEY_ENV, "anthropic": ANTHROPIC_API_KEY_ENV}
_MODEL_ENV = {"gemini": "GEMINI_MODEL", "openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL"}
# OpenAI KHONG co model mac dinh: ten model cua ho doi lien tuc, doan sai la goi that bai am tham.
_DEFAULT_MODEL = {"gemini": GEMINI_DEFAULT_MODEL, "openai": None, "anthropic": ANTHROPIC_DEFAULT_MODEL}
_LABEL = {"gemini": "Gemini", "openai": "OpenAI", "anthropic": "Claude"}

# Mo ta cho GET /api/ai: nguoi van hanh (hoac script) biet co nhung lua chon nao va moi cai can gi.
CATALOG: list[dict] = [
    {"mode": "demo", "provider": "mock", "secret_env": None, "secret_required": False,
     "default_model": None, "model_required": False, "base_url_default": None},
    {"mode": "internal", "provider": "bridge", "secret_env": INTERNAL_TOKEN_ENV, "secret_required": False,
     "default_model": None, "model_required": False, "base_url_default": None},
    {"mode": "internal", "provider": "openai_compatible", "secret_env": INTERNAL_TOKEN_ENV, "secret_required": False,
     "default_model": None, "model_required": True, "base_url_default": None},
    {"mode": "public", "provider": "gemini", "secret_env": GEMINI_API_KEY_ENV, "secret_required": True,
     "default_model": GEMINI_DEFAULT_MODEL, "model_required": False, "base_url_default": None},
    {"mode": "public", "provider": "openai", "secret_env": OPENAI_API_KEY_ENV, "secret_required": True,
     "default_model": None, "model_required": True, "base_url_default": OPENAI_DEFAULT_BASE_URL},
    {"mode": "public", "provider": "anthropic", "secret_env": ANTHROPIC_API_KEY_ENV, "secret_required": True,
     "default_model": ANTHROPIC_DEFAULT_MODEL, "model_required": False, "base_url_default": None},
]


class ProviderConfigError(ValueError):
    """Cau hinh chon che do nay nhung con thieu thu gi do. `field` chi ra thu thieu
    (vd "secrets.OPENAI_API_KEY", "public.model", "internal.base_url"); `message` tieng Viet de
    nguoi van hanh doc va sua."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def _secret(env: Mapping[str, str], name: str) -> str:
    return env.get(name, "").strip()


def _public_model(settings: AiSettings, env: Mapping[str, str]) -> str | None:
    provider = settings.public.provider
    return settings.public.model or env.get(_MODEL_ENV[provider], "").strip() or _DEFAULT_MODEL[provider]


def problems(settings: AiSettings, env: Mapping[str, str] = os.environ) -> list[ProviderConfigError]:
    """Nhung thu con thieu de CHE DO DANG CHON chay duoc. Che do khac khong bi kiem."""
    found: list[ProviderConfigError] = []
    if settings.mode == "public":
        provider = settings.public.provider
        key_env = _KEY_ENV[provider]
        if not _secret(env, key_env):
            found.append(ProviderConfigError(
                f"secrets.{key_env}", f"Chưa đặt biến môi trường {key_env} (khóa API của {_LABEL[provider]})"))
        if _public_model(settings, env) is None:
            found.append(ProviderConfigError(
                "public.model", f"Chưa chọn model cho {_LABEL[provider]} (tên model do nhà cung cấp quy định)"))
    elif settings.mode == "internal":
        if not settings.internal.base_url:
            found.append(ProviderConfigError("internal.base_url", "Chưa nhập địa chỉ chatbot nội bộ"))
        if settings.internal.protocol == "openai_compatible" and not settings.internal.model:
            found.append(ProviderConfigError("internal.model", "Chatbot nội bộ chuẩn OpenAI cần có tên model"))
    return found


def build(settings: AiSettings, env: Mapping[str, str] = os.environ) -> SuperdocProvider:
    """Dung provider cho cau hinh. Thieu thu gi thi nem ProviderConfigError (cai dau tien)."""
    found = problems(settings, env)
    if found:
        raise found[0]

    timeout = settings.timeout_sec
    if settings.mode == "demo":
        return MockSuperdocProvider()

    if settings.mode == "internal":
        cfg = settings.internal
        token = _secret(env, INTERNAL_TOKEN_ENV) or None
        if cfg.protocol == "bridge":
            return BridgeProvider(base_url=cfg.base_url, token=token, timeout_sec=timeout)
        return OpenAIProvider(base_url=cfg.base_url, model=cfg.model, api_key=token,
                              timeout_sec=timeout, name="openai_compatible")

    provider = settings.public.provider
    model = _public_model(settings, env)
    key = _secret(env, _KEY_ENV[provider])
    if provider == "gemini":
        return GeminiSuperdocProvider(api_key=key, model=model, timeout_sec=timeout)
    if provider == "anthropic":
        return AnthropicProvider(api_key=key, model=model, timeout_sec=timeout)
    return OpenAIProvider(base_url=settings.public.base_url or OPENAI_DEFAULT_BASE_URL, model=model,
                          api_key=key, timeout_sec=timeout, name="openai")


def describe(settings: AiSettings, env: Mapping[str, str] = os.environ) -> dict:
    """Che do dang co hieu luc, cho GET /api/ai va bang dieu khien. Khong chua gia tri key."""
    if settings.mode == "demo":
        return {"mode": "demo", "provider": "mock", "model": None, "base_url": None}
    if settings.mode == "internal":
        cfg = settings.internal
        return {"mode": "internal", "provider": cfg.protocol,
                "model": cfg.model if cfg.protocol == "openai_compatible" else None, "base_url": cfg.base_url}
    provider = settings.public.provider
    return {"mode": "public", "provider": provider, "model": _public_model(settings, env),
            "base_url": settings.public.base_url or (OPENAI_DEFAULT_BASE_URL if provider == "openai" else None)}
