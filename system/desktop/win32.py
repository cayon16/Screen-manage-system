"""Các lệnh Windows mà Qt không có sẵn: đo/sửa vị trí cửa sổ bằng toạ độ thật, giữ cửa sổ nổi trên
taskbar, tắt hiệu ứng phản hồi chạm, phím tắt toàn cục. Trên hệ điều hành khác mọi hàm đều không làm gì.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes as w
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

logger = logging.getLogger("pentasync.app")

IS_WINDOWS = sys.platform == "win32"

Rect = tuple[int, int, int, int]  # x, y, rộng, cao — pixel thật

HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200
MONITOR_DEFAULTTONULL = 0

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

# Các hiệu ứng Windows vẽ khi chạm (vòng tròn, ô vuông khi giữ lâu...) — không hợp màn kiosk.
_TOUCH_FEEDBACKS = (1, 4, 5, 6, 7, 11)  # CONTACTVISUALIZATION, TAP, DOUBLETAP, PRESSANDHOLD, RIGHTTAP, PRESSANDTAP

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    _user32.GetWindowRect.restype = w.BOOL
    _user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
    _user32.SetWindowPos.restype = w.BOOL
    _user32.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
    _user32.MonitorFromWindow.restype = w.HMONITOR
    _user32.IsIconic.argtypes = [w.HWND]
    _user32.IsIconic.restype = w.BOOL
    _user32.RegisterHotKey.argtypes = [w.HWND, ctypes.c_int, w.UINT, w.UINT]
    _user32.RegisterHotKey.restype = w.BOOL
    _user32.UnregisterHotKey.argtypes = [w.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = w.BOOL
    _user32.SetWindowFeedbackSetting.argtypes = [w.HWND, ctypes.c_int, w.DWORD, w.UINT, ctypes.c_void_p]
    _user32.SetWindowFeedbackSetting.restype = w.BOOL


def window_rect(hwnd: int) -> Rect | None:
    if not IS_WINDOWS or not hwnd:
        return None
    r = w.RECT()
    if not _user32.GetWindowRect(w.HWND(hwnd), ctypes.byref(r)):
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def monitor_of_window(hwnd: int) -> int:
    if not IS_WINDOWS or not hwnd:
        return 0
    return int(_user32.MonitorFromWindow(w.HWND(hwnd), MONITOR_DEFAULTTONULL) or 0)


def is_minimized(hwnd: int) -> bool:
    return bool(IS_WINDOWS and hwnd and _user32.IsIconic(w.HWND(hwnd)))


def force_rect(hwnd: int, rect: Rect, topmost: bool) -> bool:
    """Đặt cửa sổ đúng khung pixel thật của màn — dùng khi cách của Qt không ra đúng."""
    if not IS_WINDOWS or not hwnd:
        return False
    x, y, width, height = rect
    after = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    return bool(_user32.SetWindowPos(w.HWND(hwnd), w.HWND(after), x, y, width, height,
                                     SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOOWNERZORDER))


def raise_window(hwnd: int) -> bool:
    """Đưa cửa sổ lên trên các cửa sổ thường (KHÔNG cướp bàn phím, không thành "luôn trên cùng").

    Dùng cho màn hiển thị nằm trên màn chính: cửa sổ của app không nhận kích hoạt nên bất kỳ
    chương trình nào người vận hành mở ra cũng nằm đè lên nó.
    """
    if not IS_WINDOWS or not hwnd:
        return False
    return bool(_user32.SetWindowPos(w.HWND(hwnd), w.HWND(HWND_TOP), 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER))


def set_topmost(hwnd: int, topmost: bool) -> bool:
    """Nổi trên taskbar của màn đó. Gọi lại định kỳ: bấm phím Windows xong là taskbar lại nổi lên trên."""
    if not IS_WINDOWS or not hwnd:
        return False
    after = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    return bool(_user32.SetWindowPos(w.HWND(hwnd), w.HWND(after), 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER))


def disable_touch_feedback(hwnd: int) -> None:
    if not IS_WINDOWS or not hwnd:
        return
    off = w.BOOL(False)
    for feedback in _TOUCH_FEEDBACKS:
        _user32.SetWindowFeedbackSetting(w.HWND(hwnd), feedback, 0, ctypes.sizeof(off), ctypes.byref(off))


def rect_matches(actual: Rect | None, expected: Rect, tolerance: int = 1) -> bool:
    """So khung cửa sổ với khung màn. Cho lệch 1 px vì làm tròn khi đổi DPI."""
    if actual is None:
        return False
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


class GlobalHotkeys(QAbstractNativeEventFilter):
    """Phím tắt bắt được kể cả khi cửa sổ của app không được chọn (RegisterHotKey).

    Phím nào không đăng ký được (chương trình khác đã giữ) thì bỏ qua — phím tắt trong QML vẫn
    còn làm dự phòng khi cửa sổ app đang được chọn.
    """

    def __init__(self):
        super().__init__()
        self._actions: dict[int, Callable[[], None]] = {}

    def register(self, key: str, action: Callable[[], None]) -> str:
        """key: 1 chữ cái. Thử Ctrl+Shift+key, bị chiếm thì Ctrl+Alt+Shift+key.
        Trả về tổ hợp đăng ký được ("" nếu không được)."""
        if not IS_WINDOWS:
            return ""
        for mods, name in ((MOD_CONTROL | MOD_SHIFT, "Ctrl+Shift"), (MOD_CONTROL | MOD_ALT | MOD_SHIFT, "Ctrl+Alt+Shift")):
            hotkey_id = 0xB000 + len(self._actions)
            if _user32.RegisterHotKey(None, hotkey_id, mods | MOD_NOREPEAT, ord(key.upper())):
                self._actions[hotkey_id] = action
                combo = f"{name}+{key.upper()}"
                if name != "Ctrl+Shift":
                    logger.warning("Ctrl+Shift+%s đã bị chương trình khác giữ — dùng %s", key.upper(), combo)
                return combo
        logger.error("Không đăng ký được phím tắt toàn cục cho phím %s (lỗi %s)", key.upper(), ctypes.get_last_error())
        return ""

    def unregister_all(self) -> None:
        for hotkey_id in self._actions:
            _user32.UnregisterHotKey(None, hotkey_id)
        self._actions.clear()

    def nativeEventFilter(self, event_type: QByteArray, message):
        if bytes(event_type) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        msg = w.MSG.from_address(int(message))
        if msg.message != WM_HOTKEY:
            return False, 0
        action = self._actions.get(int(msg.wParam))
        if action is None:
            return False, 0
        try:
            action()
        except Exception:
            logger.exception("Lỗi khi xử lý phím tắt")
        return True, 0
