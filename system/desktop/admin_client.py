"""Kết nối WebSocket của màn quản lý (/ws/admin)."""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWebSockets import QWebSocket

from desktop.config import BACKEND_WS_URL

logger = logging.getLogger("pentasync.app")

RECONNECT_MS = 1500


class AdminClient(QObject):
    snapshotChanged = Signal()
    connectedChanged = Signal()

    def __init__(self, parent: QObject | None = None, url: str | None = None):
        super().__init__(parent)
        self._url = QUrl(url or f"{BACKEND_WS_URL}/ws/admin")
        self._connected = False
        self._snapshot: dict = {}
        self._closing = False

        self._socket = QWebSocket()
        self._socket.setParent(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.textMessageReceived.connect(self._on_text)

        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(RECONNECT_MS)
        self._retry.timeout.connect(self._open)

    def start(self) -> None:
        self._open()

    def close(self) -> None:
        self._closing = True
        self._retry.stop()
        self._socket.close()

    def _open(self) -> None:
        if not self._closing:
            self._socket.open(self._url)

    def _on_connected(self) -> None:
        self._connected = True
        self.connectedChanged.emit()

    def _on_disconnected(self) -> None:
        self._connected = False
        self.connectedChanged.emit()
        if not self._closing:
            self._retry.start()

    def _on_text(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        if msg.get("type") == "admin_snapshot":
            self._snapshot = msg
            self.snapshotChanged.emit()

    @Slot(str)
    def command(self, action: str) -> None:
        self._send({"type": "admin_command", "action": action})

    @Slot(str)
    def selectSlide(self, slide_id: str) -> None:
        self._send({"type": "admin_command", "action": "select_slide", "slide_id": slide_id})

    def _send(self, payload: dict) -> None:
        if self._connected:
            self._socket.sendTextMessage(json.dumps(payload))
        else:
            logger.warning("Màn quản lý chưa kết nối backend — bỏ lệnh %s", payload.get("action"))

    connected = Property(bool, lambda self: self._connected, notify=connectedChanged)
    snapshot = Property("QVariantMap", lambda self: self._snapshot, notify=snapshotChanged)
