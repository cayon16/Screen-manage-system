"""Giữ video chờ của mọi màn khớp nhau theo 1 đồng hồ chung.

Không truyền khung hình giữa các màn. Backend cấp mốc t0 dùng chung, mỗi màn tự tính

    target = (now_server - t0) mod duration

rồi kéo đầu phát của nó về mốc đó: lệch nhiều thì nhảy thẳng, lệch ít thì phát nhanh/chậm
hơn một chút cho mượt (nhảy liên tục sẽ thấy giật ở đường ghép giữa 2 màn).
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtMultimedia import QMediaPlayer

from desktop.config import STANDBY_SYNC_MS

HARD_SEEK_SEC = 0.3
IN_SYNC_SEC = 0.02
RATE_GAIN = 0.5
RATE_MIN = 0.85
RATE_MAX = 1.15


def target_time(now: float, t0: float, duration: float) -> float:
    return (now - t0) % duration


def drift(target: float, current: float, duration: float) -> float:
    """Khoảng cách THEO VÒNG TRÒN: lúc video vừa lặp lại, current về 0 còn target ở gần cuối.
    Trừ thẳng sẽ ra sai số gần bằng cả độ dài video rồi nhảy lung tung."""
    d = target - current
    if d > duration / 2:
        d -= duration
    elif d < -duration / 2:
        d += duration
    return d


def correction(target: float, current: float, duration: float) -> tuple[float | None, float]:
    """→ (vị trí cần nhảy tới hoặc None, tốc độ phát)."""
    d = drift(target, current, duration)
    if abs(d) > HARD_SEEK_SEC:
        return target, 1.0
    if abs(d) < IN_SYNC_SEC:
        return None, 1.0
    # Chậm hơn mốc chung (d > 0) → phát nhanh lên một chút, và ngược lại.
    return None, min(RATE_MAX, max(RATE_MIN, 1.0 + d * RATE_GAIN))


class StandbySync(QObject):
    """Mỗi cửa sổ hiển thị 1 cái. QML gọi attach() khi video chờ hiện, detach() khi ẩn."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player: QMediaPlayer | None = None
        self._t0 = 0.0
        self._offset = 0.0
        self._far_ticks = 0
        self._timer = QTimer(self)
        self._timer.setInterval(STANDBY_SYNC_MS)
        self._timer.timeout.connect(self._tick)

    @Slot(QObject, float, float, float)
    def attach(self, player: QObject, t0: float, server_now: float, received_at: float) -> None:
        self._player = player if isinstance(player, QMediaPlayer) else None
        self._t0 = t0
        self._far_ticks = 0
        # Lệch đồng hồ máy chủ ↔ máy này, đo bằng thời điểm NHẬN message chứ không phải lúc
        # gọi hàm này: lần đầu dựng view video mất cả nửa giây (nạp QtMultimedia), đo lúc đó
        # sẽ lệch đúng nửa giây và mọi màn chạy chậm hơn mốc chung.
        self._offset = server_now - received_at if server_now and received_at else 0.0
        if self._player is None:
            return
        self._timer.start()

    @Slot()
    def detach(self) -> None:
        self._timer.stop()
        self._player = None

    def _tick(self) -> None:
        player = self._player
        if player is None:
            return
        duration = player.duration() / 1000
        if duration <= 0 or not player.isSeekable():
            return
        if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            player.play()
        target = target_time(time.time() + self._offset, self._t0, duration)
        seek, rate = correction(target, player.position() / 1000, duration)
        if seek is not None:
            # Giao diện khựng một nhịp thì vị trí đọc được bị cũ và trông như lệch lớn — chỉ tua
            # khi lệch lớn 2 nhịp liền, tránh giật hình vì tua nhầm.
            self._far_ticks += 1
            if self._far_ticks < 2:
                return
            self._far_ticks = 0
            player.setPosition(int(seek * 1000))
        else:
            self._far_ticks = 0
        if abs(player.playbackRate() - rate) > 1e-3:
            player.setPlaybackRate(rate)
