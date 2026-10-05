"""Quy tắc gán vai trò cho từng màn — hàm thuần, không đụng tới Qt hay Windows.

Quy tắc (khách chốt):

    N = tổng số màn đang cắm, xếp trái → phải
    N ≥ 6 : màn Primary của Windows = MÀN QUẢN LÝ, các màn còn lại là màn hiển thị
    N ≤ 5 : tất cả là màn hiển thị (kể cả màn của máy chính)

    Trong các màn hiển thị:
      không màn nào cảm ứng → đánh số 1, 2, 3, 4, 5 lần lượt trái → phải
      có màn cảm ứng        → màn cảm ứng nhận 2, 4 (trái → phải)
                               màn không cảm ứng nhận 1, 3, 5 (trái → phải)
                               màn thừa (vd 3 màn cảm ứng) nhận số còn trống nhỏ nhất
      hết số (vd 7 màn)     → màn thừa không dùng, để nguyên màn hình Windows

Vị trí tường (wall_index) là thứ tự trái → phải của các màn hiển thị ĐƯỢC DÙNG — video chờ
cắt theo thứ tự này, không theo số vai trò.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ROLES = (1, 2, 3, 4, 5)
TOUCH_ROLES = (2, 4)
PLAIN_ROLES = (1, 3, 5)
MANAGEMENT_THRESHOLD = 6

ROLE_NAMES = {
    1: "Màn trình chiếu (trái)",
    2: "Màn điều khiển",
    3: "Màn trình chiếu (giữa)",
    4: "Màn chat chuyên dụng",
    5: "Màn trình chiếu (phải)",
}


@dataclass(frozen=True)
class Monitor:
    """1 màn vật lý. Toạ độ theo hệ toạ độ màn hình ảo của Windows (chỉ dùng để xếp thứ tự)."""

    key: str  # định danh ổn định trong 1 lần chạy, vd "\\\\.\\DISPLAY3"
    x: int
    y: int
    width: int
    height: int
    primary: bool = False
    touch: bool = False


@dataclass(frozen=True)
class Display:
    monitor: Monitor
    role: int
    wall_index: int


@dataclass(frozen=True)
class Assignment:
    management: Monitor | None
    displays: tuple[Display, ...]  # xếp theo wall_index
    unused: tuple[Monitor, ...] = field(default_factory=tuple)

    def as_layout_request(self) -> dict:
        """Thân của POST /api/layout."""
        return {"displays": [{"role": d.role, "wall_index": d.wall_index} for d in self.displays]}


def _left_to_right(monitors) -> list[Monitor]:
    return sorted(monitors, key=lambda m: (m.x, m.y, m.key))


def assign(monitors) -> Assignment:
    ordered = _left_to_right(monitors)
    if not ordered:
        return Assignment(management=None, displays=())

    management = None
    if len(ordered) >= MANAGEMENT_THRESHOLD:
        # Windows luôn có đúng 1 màn Primary; phòng hờ không thấy thì lấy màn trái cùng.
        management = next((m for m in ordered if m.primary), ordered[0])
        ordered = [m for m in ordered if m is not management]

    roles: dict[str, int] = {}
    if not any(m.touch for m in ordered):
        # zip dừng khi hết vai trò: màn thứ 6 trở đi không được dùng.
        for monitor, role in zip(ordered, ROLES, strict=False):
            roles[monitor.key] = role
    else:
        touch = [m for m in ordered if m.touch]
        plain = [m for m in ordered if not m.touch]
        for monitor, role in zip(touch, TOUCH_ROLES, strict=False):
            roles[monitor.key] = role
        for monitor, role in zip(plain, PLAIN_ROLES, strict=False):
            roles[monitor.key] = role
        leftovers = [m for m in ordered if m.key not in roles]
        free = [r for r in ROLES if r not in roles.values()]
        for monitor, role in zip(leftovers, free, strict=False):
            roles[monitor.key] = role

    used = [m for m in ordered if m.key in roles]
    displays = tuple(
        Display(monitor=m, role=roles[m.key], wall_index=i) for i, m in enumerate(used)
    )
    unused = tuple(m for m in ordered if m.key not in roles)
    return Assignment(management=management, displays=displays, unused=unused)
