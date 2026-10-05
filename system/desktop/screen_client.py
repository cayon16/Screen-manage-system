"""Kết nối WebSocket của 1 màn hiển thị, phơi trạng thái cho QML.

Không tự quyết định trạng thái nào: backend gửi gì thì hiện nấy. Riêng lịch sử chat thì giữ ở
đây (backend chỉ gửi câu trả lời của AI, câu hỏi do màn tự thêm vào khi gửi), gắn với
session_id — đổi phiên là xoá sạch, đúng yêu cầu "xoá lịch sử khi kết thúc".
"""

from __future__ import annotations

import json
import logging
import time

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtWebSockets import QWebSocket

from desktop.config import BACKEND_URL, BACKEND_WS_URL

logger = logging.getLogger("pentasync.app")

RECONNECT_MIN_MS = 1000
RECONNECT_MAX_MS = 5000


class ChatModel(QAbstractListModel):
    RoleRole = Qt.ItemDataRole.UserRole + 1
    TextRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._items: list[tuple[str, str]] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008 (chu ky bat buoc cua Qt)
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        who, text = self._items[index.row()]
        if role == self.RoleRole:
            return who
        if role in (self.TextRole, Qt.ItemDataRole.DisplayRole):
            return text
        return None

    def roleNames(self):
        return {self.RoleRole: QByteArray(b"who"), self.TextRole: QByteArray(b"text")}

    def append(self, who: str, text: str) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append((who, text))
        self.endInsertRows()

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def items(self) -> list[tuple[str, str]]:
        return list(self._items)


class ScreenClient(QObject):
    changed = Signal()
    chatChanged = Signal()
    tier1Changed = Signal()
    connectedChanged = Signal()

    def __init__(self, role: int, parent: QObject | None = None, url: str | None = None):
        super().__init__(parent)
        self._role = role
        self._url = QUrl(url or f"{BACKEND_WS_URL}/ws/{role}")
        self._connected = False
        self._view = "connecting"
        self._state = ""
        self._data: dict = {}
        self._session_id = ""
        self._waiting = False
        self._in_error = False
        self._error_text = ""
        self._tier1_visible = False
        self._tier1_seconds = 0
        self._tier1_session = ""
        self._tier1_serial = 0
        self._model = ChatModel(self)
        self._closing = False

        self._socket = QWebSocket()
        self._socket.setParent(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.textMessageReceived.connect(self._on_text)

        self._retry_ms = RECONNECT_MIN_MS
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self._open)

    # ---------- vòng đời ----------

    def start(self) -> None:
        self._open()

    def close(self) -> None:
        self._closing = True
        self._retry.stop()
        self._socket.close()

    def _open(self) -> None:
        if self._closing:
            return
        self._socket.open(self._url)

    def _on_connected(self) -> None:
        self._retry_ms = RECONNECT_MIN_MS
        self._connected = True
        self.connectedChanged.emit()
        # Không cần chào hỏi: backend gửi state_update ngay khi nhận kết nối.

    def _on_disconnected(self) -> None:
        if self._connected and not self._closing:
            logger.warning("Màn %s mất kết nối backend", self._role)
        self._connected = False
        self.connectedChanged.emit()
        if not self._closing:
            self._retry.start(self._retry_ms)
            self._retry_ms = min(self._retry_ms * 2, RECONNECT_MAX_MS)

    # ---------- nhận ----------

    def _on_text(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            logger.warning("Màn %s nhận message không phải JSON", self._role)
            return
        self.handle_message(msg)

    def handle_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "state_update":
            self._on_state(msg)
        elif kind == "chat_message_ack":
            if msg.get("session_id") == self._session_id:
                self._model.append("assistant", msg.get("text", ""))
        elif kind == "error":
            if msg.get("session_id") == self._session_id:
                self._error_text = msg.get("message", "")
                self.chatChanged.emit()
        elif kind == "session_closed":
            self._reset_chat("")
        elif kind == "confirm_prompt":
            if msg.get("kind") == "tier1_warning":
                self._tier1_visible = True
                self._tier1_seconds = int(msg.get("timeout_sec") or 0)
                self._tier1_session = msg.get("session_id") or ""
                self._tier1_serial += 1
                self.tier1Changed.emit()
            # "mode_switch": hộp thoại hiện theo state CHAT_CONFIRM_SWITCH, không cần message.
        else:
            logger.debug("Màn %s bỏ qua message %r", self._role, kind)

    def _on_state(self, msg: dict) -> None:
        data = msg.get("data") or {}
        view = msg.get("view", "")
        session_id = data.get("session_id") or ""
        if view != "chat":
            session_id = ""
        if session_id != self._session_id:
            self._reset_chat(session_id)

        self._view = view
        self._state = msg.get("state", "")
        if view == "standby":
            data = {**data, "received_at": time.time()}
        self._data = data
        self._waiting = bool(data.get("waiting_for_ai"))
        self._in_error = bool(data.get("in_error"))

        # Mọi hộp "còn ở đó không" đều hết ý nghĩa khi trạng thái đổi (giống bản web cũ).
        self._hide_tier1()
        self.changed.emit()
        self.chatChanged.emit()

    def _reset_chat(self, session_id: str) -> None:
        self._session_id = session_id
        self._error_text = ""
        self._waiting = False
        self._model.clear()
        self._hide_tier1()
        self.chatChanged.emit()

    def _hide_tier1(self) -> None:
        if self._tier1_visible:
            self._tier1_visible = False
            self.tier1Changed.emit()

    # ---------- gửi ----------

    def _send(self, payload: dict) -> None:
        if not self._connected:
            return
        self._socket.sendTextMessage(json.dumps(payload, ensure_ascii=False))

    @Slot(str)
    def touch(self, target: str) -> None:
        self._send({"type": "touch_event", "screen_id": self._role, "target": target})

    @Slot(str, result=bool)
    def sendChat(self, text: str) -> bool:
        text = text.strip()
        if not text or not self._session_id or self._waiting or not self._connected:
            return False
        self._model.append("user", text)
        self._error_text = ""
        # Khoá ô nhập ngay, không chờ backend: bấm gửi 2 lần liền sẽ thành 2 lượt hỏi liên tiếp.
        self._waiting = True
        self.chatChanged.emit()
        self._send(
            {"type": "chat_message", "screen_id": self._role, "session_id": self._session_id, "text": text}
        )
        return True

    @Slot()
    def ackTier1(self) -> None:
        if not self._tier1_visible:
            return
        self._send({"type": "tier1_ack", "screen_id": self._role, "session_id": self._tier1_session})
        self._hide_tier1()

    @Slot(str)
    def selectSlide(self, slide_id: str) -> None:
        self._send({"type": "select_slide", "screen_id": self._role, "slide_id": slide_id})

    @Slot(str, result=str)
    def mediaUrl(self, path: str) -> str:
        """Đường dẫn HTTP của backend ("/media/x.png") → URL đầy đủ cho QML."""
        return f"{BACKEND_URL}{path}" if path.startswith("/") else path

    # ---------- thuộc tính cho QML ----------

    role = Property(int, lambda self: self._role, constant=True)
    connected = Property(bool, lambda self: self._connected, notify=connectedChanged)
    view = Property(str, lambda self: self._view, notify=changed)
    state = Property(str, lambda self: self._state, notify=changed)
    data = Property("QVariantMap", lambda self: self._data, notify=changed)
    sessionId = Property(str, lambda self: self._session_id, notify=chatChanged)
    waitingForAi = Property(bool, lambda self: self._waiting, notify=chatChanged)
    inError = Property(bool, lambda self: self._in_error, notify=chatChanged)
    errorText = Property(str, lambda self: self._error_text, notify=chatChanged)
    messages = Property(QObject, lambda self: self._model, constant=True)
    tier1Visible = Property(bool, lambda self: self._tier1_visible, notify=tier1Changed)
    tier1Seconds = Property(int, lambda self: self._tier1_seconds, notify=tier1Changed)
    tier1Serial = Property(int, lambda self: self._tier1_serial, notify=tier1Changed)
