from __future__ import annotations

from typing import Sequence
from urllib.parse import quote

import httpx

from app.config import SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc.base import ChatContext, SuperdocError, Turn, normalize_history
from app.superdoc.http_common import to_superdoc_error

logger = get_logger()

_LABEL = "Chatbot nội bộ"


class BridgeProvider:
    """Ket noi chatbot noi bo cong ty theo chuan "Superdoc Bridge v1" (xem docs/superdoc_bridge_api.md).

    Chi bridge (mang noi bo) moi duoc nhan session_id va screen_id; bot co the dung chung de giu
    phien phia no, va nhan end_session de biet khi nao dong.
    """

    name = "bridge"
    model = None

    def __init__(self, *, base_url: str, token: str | None = None, timeout_sec: float = SUPERDOC_TIMEOUT_SEC):
        self._base = base_url.rstrip("/")
        headers = {"X-PentaSync-Bridge": "1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(timeout=timeout_sec, headers=headers)

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        turns = normalize_history(history)
        if not turns:
            raise SuperdocError("history rong — khong co gi de tra loi", code="bad_response")

        payload = {
            "session_id": context.session_id,
            "screen": context.screen_id,
            "locale": "vi-VN",
            "system_prompt": context.system_prompt,
            "messages": [{"role": t.role, "content": t.text} for t in turns],
        }
        try:
            response = await self._client.post(f"{self._base}/v1/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise to_superdoc_error(exc, _LABEL) from exc

        text = data.get("reply") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise SuperdocError(f"{_LABEL} trả về dữ liệu không đúng chuẩn", code="bad_response")
        if not text.strip():
            raise SuperdocError(f"{_LABEL} trả về câu trả lời rỗng", code="empty_reply")
        return text.strip()

    async def end_session(self, context: ChatContext, reason: str) -> None:
        url = f"{self._base}/v1/sessions/{quote(context.session_id, safe='')}/end"
        try:
            response = await self._client.post(url, json={"reason": reason})
            # 404/405: bot khong ho tro dong phien (khong bat buoc theo chuan) — khong phai loi.
            if response.status_code in (404, 405):
                return
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise to_superdoc_error(exc, _LABEL) from exc

    async def aclose(self) -> None:
        await self._client.aclose()
