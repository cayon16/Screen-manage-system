from __future__ import annotations

from typing import Sequence

from app.superdoc.base import ChatContext, SuperdocError, Turn


class UnavailableProvider:
    """Thay cho provider that khi cau hinh sai (thieu key, thieu dia chi...).

    CO Y khong lui ve mock: man hinh benh vien ma tra loi bang du lieu gia (gio kham, vi tri khoa
    bia san) con nguy hiem hon la bao thang "chua ket noi duoc". Moi cau hoi deu that bai voi
    thong bao chung tren man hinh; ly do that nam trong log va trong GET /api/ai.
    """

    name = "unavailable"
    model = None

    def __init__(self, reason: str):
        self.reason = reason

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        raise SuperdocError(self.reason, code="not_configured")

    async def end_session(self, context: ChatContext, reason: str) -> None:
        return None

    async def aclose(self) -> None:
        return None
