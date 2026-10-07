from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger

logger = get_logger()


def _clean_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise ValueError("Địa chỉ phải bắt đầu bằng http:// hoặc https://")
    return value.rstrip("/")


class InternalSettings(BaseModel):
    """Chatbot noi bo cua cong ty."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["bridge", "openai_compatible"] = "bridge"
    base_url: str | None = None  # vd "http://10.0.0.20:9000"; bat buoc khi mode=internal
    model: str | None = None  # chi openai_compatible (bat buoc khi do)

    _url = field_validator("base_url")(_clean_url)


class PublicSettings(BaseModel):
    """AI cong khai (Google / OpenAI / Anthropic)."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini", "openai", "anthropic"] = "gemini"
    model: str | None = None  # None = mac dinh cua provider; openai KHONG co mac dinh
    base_url: str | None = None  # chi openai; None = https://api.openai.com/v1

    _url = field_validator("base_url")(_clean_url)


class AiSettings(BaseModel):
    """Cau hinh AI luu o ai_settings.json. KHONG co truong nao chua API key — ve cau truc khong the
    luu nham key vao file. Validator chi kiem HINH DANG; do day du theo che do do registry.problems()
    kiem, nen co the luu cau hinh `internal` do dang trong luc van chay `public`."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mode: Literal["demo", "internal", "public"] = "demo"
    internal: InternalSettings = Field(default_factory=InternalSettings)
    public: PublicSettings = Field(default_factory=PublicSettings)
    timeout_sec: float = Field(SUPERDOC_TIMEOUT_SEC, ge=5, le=60)
    system_prompt: str | None = Field(None, max_length=4000)  # None = SUPERDOC_SYSTEM_PROMPT


def settings_from_env(env: Mapping[str, str] = os.environ) -> AiSettings:
    """Cau hinh khoi dau khi chua co file — giu tuong thich ban cu (SUPERDOC_PROVIDER=gemini)."""
    try:
        name = env.get("SUPERDOC_PROVIDER", "mock").strip().lower()
        provider = name if name in ("gemini", "openai", "anthropic") else "gemini"
        return AiSettings(
            mode="public" if name in ("gemini", "openai", "anthropic") else "demo",
            internal=InternalSettings(base_url=env.get("SUPERDOC_INTERNAL_URL") or None),
            public=PublicSettings(provider=provider, model=env.get(f"{provider.upper()}_MODEL") or None),
        )
    except ValueError as exc:
        logger.error("Bien moi truong cau hinh AI khong hop le (%s) — dung che do demo", exc)
        return AiSettings()


def load_settings(path: Path | None, env: Mapping[str, str] = os.environ) -> AiSettings:
    """Doc file neu co (khi do bien moi truong KHONG ghi de file), khong thi dung bien moi truong."""
    if path is not None and path.is_file():
        try:
            return AiSettings.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.error("File cau hinh AI hong (%s) — dung cau hinh mac dinh tu bien moi truong", exc)
    return settings_from_env(env)


def save_settings(path: Path, settings: AiSettings) -> None:
    """Ghi nguyen tu (file tam roi doi ten): mat dien giua chung khong de lai file hong."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(settings.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
