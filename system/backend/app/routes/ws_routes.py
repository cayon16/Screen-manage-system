from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.commands import (
    AdminCommand,
    AdminConnectedCommand,
    ChatMessageCommand,
    ClientConnectedCommand,
    ClientDisconnectedCommand,
    Command,
    SelectSlideCommand,
    Tier1AckCommand,
    TouchCommand,
)
from app.config import ALL_SCREENS
from app.logging_setup import get_logger
from app.schemas import AdminCommandMsg, ClientMessage, parse_client_message
from app.state.cluster_controller import ClusterController
from app.state.ws_manager import ConnectionManager

logger = get_logger()

router = APIRouter()


def _to_command(msg: ClientMessage) -> Command | None:
    if msg.type == "touch_event":
        return TouchCommand(screen_id=msg.screen_id, target=msg.target)
    if msg.type == "chat_message":
        return ChatMessageCommand(screen_id=msg.screen_id, session_id=msg.session_id, text=msg.text)
    if msg.type == "tier1_ack":
        return Tier1AckCommand(screen_id=msg.screen_id, session_id=msg.session_id)
    if msg.type == "select_slide":
        return SelectSlideCommand(screen_id=msg.screen_id, slide_id=msg.slide_id)
    return None


# Phai dang ky TRUOC "/ws/{screen_id}", neu khong "/ws/admin" bi route kia bat mat (va tu choi
# vi "admin" khong phai so).
@router.websocket("/ws/admin")
async def admin_websocket_endpoint(websocket: WebSocket) -> None:
    manager: ConnectionManager = websocket.app.state.connection_manager
    cluster: ClusterController = websocket.app.state.cluster

    await manager.connect_admin(websocket)
    # Controller se gui anh chup toan canh ngay sau lenh nay — man quan ly khong phai doi.
    await cluster.submit(AdminConnectedCommand())

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                logger.warning("Payload khong phai JSON hop le tu man quan ly")
                continue

            try:
                msg = AdminCommandMsg.model_validate(raw)
            except ValidationError:
                logger.warning("Lenh quan ly khong hop le: %r", raw)
                continue

            await cluster.submit(AdminCommand(action=msg.action, slide_id=msg.slide_id))
    finally:
        manager.disconnect_admin(websocket)


@router.websocket("/ws/{screen_id}")
async def websocket_endpoint(websocket: WebSocket, screen_id: int) -> None:
    if screen_id not in ALL_SCREENS:
        await websocket.close(code=4004)
        return

    manager: ConnectionManager = websocket.app.state.connection_manager
    cluster: ClusterController = websocket.app.state.cluster

    # Man vua mo lai co the ket noi moi TRUOC khi ket noi cu kip bao ngat — dinh danh tung ket
    # noi de tin "ngat" den muon cua ket noi cu khong xoa nham ket noi moi.
    conn_id = uuid.uuid4().hex
    await manager.connect(screen_id, websocket)
    await cluster.submit(ClientConnectedCommand(screen_id=screen_id, conn_id=conn_id))

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                # receive_json() lam json.loads() noi bo — payload khong phai JSON hop le.
                # Bo qua message nay, KHONG ngat ket noi (khac voi disconnect that su).
                logger.warning("Payload khong phai JSON hop le tu screen_id=%s", screen_id)
                continue

            try:
                msg = parse_client_message(raw)
            except Exception:
                logger.warning("Payload WS khong hop le tu screen_id=%s: %r", screen_id, raw)
                continue

            if msg.screen_id != screen_id:
                # Kenh WS gan voi 1 screen_id co dinh theo URL — screen_id trong body phai khop,
                # tranh 1 bug frontend tuong lai vo tinh gui nham lam sai lech state man khac.
                logger.warning(
                    "Message screen_id=%s khong khop ket noi /ws/%s — bo qua.", msg.screen_id, screen_id
                )
                continue

            command = _to_command(msg)
            if command is not None:
                await cluster.submit(command)
    finally:
        manager.disconnect(screen_id, websocket)
        await cluster.submit(ClientDisconnectedCommand(screen_id=screen_id, conn_id=conn_id))
