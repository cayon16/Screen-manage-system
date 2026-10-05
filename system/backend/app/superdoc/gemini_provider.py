from __future__ import annotations

from typing import Sequence

import httpx

from app.config import GEMINI_API_KEY, GEMINI_MODEL, SUPERDOC_SYSTEM_PROMPT, SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc.base import SuperdocError, Turn

logger = get_logger()

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiSuperdocProvider:
    """Goi Gemini API — dung tam thay cho chatbot Superdoc that (khach chua co tai lieu API).

    Chi dung 1 endpoint generateContent, khong stream: cau tra loi ngan (toi da 4 cau theo
    system prompt) nen doi tron goi don gian hon nhieu so voi ghep tung chunk stream.
    """

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        # Doc config luc GOI chu khong dat lam gia tri mac dinh cua tham so: gia tri mac dinh
        # duoc chot ngay khi Python nap module, nen sau do doi config se khong con tac dung.
        api_key = api_key if api_key is not None else GEMINI_API_KEY
        model = model if model is not None else GEMINI_MODEL
        if not api_key:
            raise ValueError("GEMINI_API_KEY chua duoc dat — khong the dung provider gemini")
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=SUPERDOC_TIMEOUT_SEC)

    async def reply(self, history: Sequence[Turn]) -> str:
        if not history:
            raise SuperdocError("history rong — khong co gi de tra loi")

        payload = {
            "system_instruction": {"parts": [{"text": SUPERDOC_SYSTEM_PROMPT}]},
            "contents": [
                # Gemini goi vai tro cua AI la "model", khac ten voi "assistant" dung noi bo.
                {"role": "model" if t.role == "assistant" else "user", "parts": [{"text": t.text}]}
                for t in history
            ],
        }

        try:
            response = await self._client.post(
                f"{_API_BASE}/{self._model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            # Khong log body vi co the chua noi dung nguoi dung vua go.
            raise SuperdocError(f"Gemini tra ve HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise SuperdocError(f"Khong goi duoc Gemini: {type(exc).__name__}") from exc

        text = _extract_text(data)
        if not text:
            # Vd bi chan boi bo loc an toan, hoac finishReason != STOP.
            logger.warning("Gemini tra ve phan hoi khong co text (finish=%s)", _finish_reason(data))
            raise SuperdocError("Gemini khong tra ve noi dung nao")
        return text

    async def end_session(self, session_id: str) -> None:
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
