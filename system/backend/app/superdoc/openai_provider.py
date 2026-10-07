from __future__ import annotations

from typing import Sequence

import httpx

from app.config import SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc.base import ChatContext, SuperdocError, Turn, normalize_history
from app.superdoc.http_common import to_superdoc_error

logger = get_logger()

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    """Goi API theo chuan Chat Completions (POST {base_url}/chat/completions).

    Dung cho 2 viec: GPT cua OpenAI (name="openai") va chatbot noi bo noi chuan OpenAI nhu vLLM,
    Ollama, LiteLLM, Dify... (name="openai_compatible"). Chuan nay cung la chuan chung ma Azure
    va nhieu dich vu khac chap nhan. Khong gui tham so gioi han token de tuong thich may chu khac.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_sec: float = SUPERDOC_TIMEOUT_SEC,
        name: str = "openai",
    ):
        self.name = name
        self.model = model
        self._label = "OpenAI" if name == "openai" else "Chatbot nội bộ"
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        # Chatbot noi bo co the khong can key: khi do khong gui header Authorization.
        self._api_key = api_key or None
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        turns = normalize_history(history)
        if not turns:
            raise SuperdocError("history rong — khong co gi de tra loi", code="bad_response")

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": context.system_prompt}]
            + [{"role": t.role, "content": t.text} for t in turns],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        try:
            response = await self._client.post(self._url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Khong log body vi co the chua noi dung nguoi dung vua go.
            raise to_superdoc_error(exc, self._label) from exc

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise SuperdocError(f"{self._label} trả về dữ liệu không đúng chuẩn", code="bad_response")
        choice = choices[0]
        message = choice.get("message") or {}

        text = _message_text(message)
        if not text:
            blocked = choice.get("finish_reason") == "content_filter" or bool(message.get("refusal"))
            logger.warning("%s tra ve phan hoi khong co text (finish=%s)", self.name, choice.get("finish_reason"))
            raise SuperdocError(
                f"{self._label} không trả về nội dung nào", code="filtered" if blocked else "empty_reply"
            )
        return text

    async def end_session(self, context: ChatContext, reason: str) -> None:
        # Chat Completions la stateless: toan bo ngu canh nam trong tung request.
        return None

    async def aclose(self) -> None:
        await self._client.aclose()


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        # Mot so may chu tra noi dung dang danh sach cac khoi {"type": "text", "text": ...}.
        return "".join(p.get("text", "") for p in content if isinstance(p, dict)).strip()
    return ""
