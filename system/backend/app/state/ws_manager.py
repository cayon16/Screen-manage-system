from __future__ import annotations

from fastapi import WebSocket

from app.logging_setup import get_logger
from app.schemas import AdminSnapshotMsg, ServerMessage

logger = get_logger()


class ConnectionManager:
    """Anh xa screen_id -> WebSocket dang mo, cong them cac ket noi cua man quan ly. Day la
    callback `send`/`send_admin` ma ClusterController dung de goi ra ngoai — ClusterController
    khong biet gi ve FastAPI/WebSocket."""

    def __init__(self):
        self._connections: dict[int, WebSocket] = {}
        self._admins: set[WebSocket] = set()

    async def connect(self, screen_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[screen_id] = websocket

    def disconnect(self, screen_id: int, websocket: WebSocket) -> None:
        if self._connections.get(screen_id) is websocket:
            del self._connections[screen_id]

    async def send_to(self, screen_id: int, message: ServerMessage) -> None:
        ws = self._connections.get(screen_id)
        if ws is None:
            return
        try:
            await ws.send_text(message.model_dump_json())
        except Exception:
            logger.exception("Gui WebSocket that bai cho screen_id=%s", screen_id)

    # ---------- man quan ly ----------

    async def connect_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._admins.add(websocket)

    def disconnect_admin(self, websocket: WebSocket) -> None:
        self._admins.discard(websocket)

    async def send_admin(self, message: AdminSnapshotMsg) -> None:
        payload = message.model_dump_json()
        for ws in list(self._admins):
            try:
                await ws.send_text(payload)
            except Exception:
                logger.warning("Gui anh chup cho man quan ly that bai — bo ket noi do")
                self._admins.discard(ws)
