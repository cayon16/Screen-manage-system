from __future__ import annotations

from typing import Sequence

import httpx

from app.config import SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc.base import ChatContext, SuperdocError, Turn, normalize_history
from app.superdoc.http_common import to_superdoc_error

logger = get_logger()

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_BLOCKED_FINISH = frozenset({"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"})


class GeminiSuperdocProvider:
    """Goi Gemini API (Google).

    Chi dung 1 endpoint generateContent, khong stream: cau tra loi ngan (toi da 4 cau theo
    system prompt) nen doi tron goi don gian hon nhieu so voi ghep tung chunk stream.
    """

    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_sec: float = SUPERDOC_TIMEOUT_SEC):
        if not api_key:
            raise ValueError("Thiếu API key Gemini")
        self._api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        turns = normalize_history(history)
        if not turns:
            raise SuperdocError("history rong — khong co gi de tra loi", code="bad_response")

        payload = {
            "system_instruction": {"parts": [{"text": context.system_prompt}]},
            "contents": [
                # Gemini goi vai tro cua AI la "model", khac ten voi "assistant" dung noi bo.
                {"role": "model" if t.role == "assistant" else "user", "parts": [{"text": t.text}]}
                for t in turns
            ],
        }

        try:
            response = await self._client.post(
                f"{_API_BASE}/{self.model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Khong log body vi co the chua noi dung nguoi dung vua go.
            raise to_superdoc_error(exc, "Gemini") from exc

        text = _extract_text(data)
        if not text:
            # Vd bi chan boi bo loc an toan, hoac finishReason != STOP.
            finish = _finish_reason(data)
            logger.warning("Gemini tra ve phan hoi khong co text (finish=%s)", finish)
            blocked = finish in _BLOCKED_FINISH or bool((data.get("promptFeedback") or {}).get("blockReason"))
            raise SuperdocError("Gemini không trả về nội dung nào", code="filtered" if blocked else "empty_reply")
        return text

    async def end_session(self, context: ChatContext, reason: str) -> None:
        # generateContent la stateless: toan bo ngu canh nam trong tung request, phia Gemini
        # khong luu phien nao de dong.
        return None

    async def aclose(self) -> None:
        await self._client.aclose()


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def _finish_reason(data: dict) -> str:
    candidates = data.get("candidates") or []
    return candidates[0].get("finishReason", "?") if candidates else "no_candidates"
