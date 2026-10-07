from __future__ import annotations

from typing import Sequence

import httpx

from app.config import SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc.base import ChatContext, SuperdocError, Turn, normalize_history
from app.superdoc.http_common import to_superdoc_error

logger = get_logger()

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
# Bat buoc co (thieu la HTTP 400). Cau tra loi toi da 4 cau nen 1024 la rat du.
_MAX_TOKENS = 1024


class AnthropicProvider:
    """Goi Messages API cua Anthropic (Claude). System prompt di rieng o cap tren cung."""

    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, timeout_sec: float = SUPERDOC_TIMEOUT_SEC):
        if not api_key:
            raise ValueError("Thiếu API key Anthropic")
        self._api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        turns = normalize_history(history)
        if not turns:
            raise SuperdocError("history rong — khong co gi de tra loi", code="bad_response")

        payload = {
            "model": self.model,
            "max_tokens": _MAX_TOKENS,
            "system": context.system_prompt,
            "messages": [{"role": t.role, "content": t.text} for t in turns],
        }
        headers = {"x-api-key": self._api_key, "anthropic-version": _API_VERSION}

        try:
            response = await self._client.post(_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Loi 529 la Anthropic dang qua tai: to_superdoc_error ghi thanh http_529.
            raise to_superdoc_error(exc, "Claude") from exc

        if not isinstance(data, dict):
            raise SuperdocError("Claude trả về dữ liệu không đúng chuẩn", code="bad_response")
        blocks = data.get("content") or []
        text = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
        if not text:
            stop = data.get("stop_reason")
            logger.warning("Claude tra ve phan hoi khong co text (stop_reason=%s)", stop)
            raise SuperdocError(
                "Claude không trả về nội dung nào", code="filtered" if stop == "refusal" else "empty_reply"
            )
        return text

    async def end_session(self, context: ChatContext, reason: str) -> None:
        # Messages API la stateless: toan bo ngu canh nam trong tung request.
        return None

    async def aclose(self) -> None:
        await self._client.aclose()
