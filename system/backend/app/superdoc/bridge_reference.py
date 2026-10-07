"""May chu MAU theo chuan Superdoc Bridge v1 — de IT cong ty xem ban lam dung nghia la gi, va de
test hop dong cua BridgeProvider.

    cd backend
    python -m app.superdoc.bridge_reference --port 9000 [--token abc]

Tra loi bang MockSuperdocProvider (theo tu khoa). KHONG gan vao app chinh cua PentaSync.
Mo ta chuan day du: docs/superdoc_bridge_api.md.
"""

from __future__ import annotations

import argparse
import hmac
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.superdoc.base import ChatContext, Turn
from app.superdoc.mock_provider import MockSuperdocProvider


class _Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class _ChatRequest(BaseModel):
    session_id: str
    screen: int
    locale: str = "vi-VN"
    system_prompt: str
    messages: list[_Message]


class _EndRequest(BaseModel):
    reason: str


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(token: str | None = None, latency_sec: float = 0.2) -> FastAPI:
    """Dung may chu mau. `received` dem so cau hoi nhan duoc, `ended` luu (phien, ly do) da dong."""
    app = FastAPI(title="Superdoc Bridge v1 — may chu mau")
    app.state.received = 0
    app.state.ended = []
    bot = MockSuperdocProvider(latency_sec=latency_sec)

    def authorized(request: Request) -> bool:
        if not token:
            return True
        return hmac.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}")

    @app.post("/v1/chat")
    async def chat(body: _ChatRequest, request: Request):
        if not authorized(request):
            return _error(401, "unauthorized", "Sai hoặc thiếu token")
        if not body.messages or body.messages[-1].role != "user":
            return _error(422, "bad_messages", "Lượt cuối cùng phải là của người dùng")
        app.state.received += 1
        context = ChatContext(body.session_id, body.screen, body.system_prompt)
        reply = await bot.reply([Turn(m.role, m.content) for m in body.messages], context)
        return {"reply": reply}

    @app.post("/v1/sessions/{session_id}/end", status_code=204)
    async def end_session(session_id: str, body: _EndRequest, request: Request):
        if not authorized(request):
            return _error(401, "unauthorized", "Sai hoặc thiếu token")
        app.state.ended.append((session_id, body.reason))
        return Response(status_code=204)

    @app.get("/v1/health")
    async def health():
        return {"status": "ok"}

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="May chu mau Superdoc Bridge v1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--token", default=None, help="Neu dat, moi request phai kem Authorization: Bearer <token>")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(args.token), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
