from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from app.state.layout import ClusterLayout

# Command = từ vựng nội bộ mà orchestrator_loop tiêu thụ. Mọi mutation state (dù đến từ
# WebSocket hay từ 1 timer hết hạn) đều được quy về 1 Command rồi xử lý tuần tự qua 1 hàng đợi
# duy nhất — không có code path nào khác được phép sửa state trực tiếp.


@dataclass
class TouchCommand:
    screen_id: int
    target: str


@dataclass
class ChatMessageCommand:
    screen_id: int
    session_id: str
    text: str


@dataclass
class Tier1AckCommand:
    screen_id: int
    session_id: str


@dataclass
class Tier1WarningFiredCommand:
    """Timer cảnh báo Tier-1 hết hạn — phát confirm_prompt và khởi động timer cleanup."""

    screen_id: int
    session_id: str


@dataclass
class Tier1CleanupFiredCommand:
    """Timer cleanup Tier-1 hết hạn — hủy AI task, xóa lịch sử, đóng session, về Standby."""

    screen_id: int
    session_id: str


@dataclass
class AiReplyReadyCommand:
    """Task gọi AI đã trả về thành công — ghi vào lịch sử, gửi ra màn, khởi động lại Tier-1."""

    screen_id: int
    session_id: str
    text: str


@dataclass
class AiReplyFailedCommand:
    """Task gọi AI thất bại (mất mạng, timeout, API từ chối) — chỉ ảnh hưởng đúng màn này."""

    screen_id: int
    session_id: str
    code: str
    message: str


@dataclass
class SelectSlideCommand:
    """Màn 2 bấm 1 trong 6 nút — ghim slide tương ứng lên đúng màn phụ trách nó."""

    screen_id: int  # màn gửi lệnh (luôn là Màn 2)
    slide_id: str


@dataclass
class HostActivityCommand:
    """Có người thao tác chuột/phím trên máy chủ — tính như một tương tác thật."""


@dataclass
class Tier2FiredCommand:
    """Timer cluster hết hạn — đưa cả 5 màn về Standby."""


@dataclass
class ErrorCleanupFiredCommand:
    screen_id: int
    session_id: str


@dataclass
class ClientConnectedCommand:
    """Màn hình (re)connect WebSocket — gửi lại state_update snapshot hiện tại."""

    screen_id: int
    # Định danh của đúng kết nối này. Khi 1 màn nối lại, lệnh "mất kết nối" của kết nối CŨ có thể
    # tới SAU lệnh "đã kết nối" của kết nối MỚI; so conn_id để không đánh dấu nhầm màn là mất kết nối.
    conn_id: str = ""


@dataclass
class ClientDisconnectedCommand:
    screen_id: int
    conn_id: str = ""


@dataclass
class LayoutCommand:
    """App Qt báo bố cục màn thực tế: vai trò nào đang có và đứng ở vị trí nào trong dãy."""

    layout: "ClusterLayout"


@dataclass
class AdminCommand:
    """Lệnh từ màn quản lý.

    action: select_slide | force_standby | blackout_on | blackout_off | reset | refresh
    """

    action: str
    slide_id: str | None = None


@dataclass
class AdminConnectedCommand:
    """Có màn quản lý vừa kết nối — gửi ngay ảnh chụp trạng thái hiện tại."""


@dataclass
class SlicesReadyCommand:
    """Đã cắt xong video chờ thành `wall_count` lát — các màn chờ đổi sang phát lát riêng."""

    wall_count: int


Command = Union[
    TouchCommand,
    ChatMessageCommand,
    Tier1AckCommand,
    AiReplyReadyCommand,
    AiReplyFailedCommand,
    SelectSlideCommand,
    HostActivityCommand,
    Tier1WarningFiredCommand,
    Tier1CleanupFiredCommand,
    Tier2FiredCommand,
    ErrorCleanupFiredCommand,
    ClientConnectedCommand,
    ClientDisconnectedCommand,
    LayoutCommand,
    AdminCommand,
    AdminConnectedCommand,
    SlicesReadyCommand,
]
