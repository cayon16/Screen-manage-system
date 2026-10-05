"""Đọc danh sách màn thật: QScreen của Qt + thông tin Windows (tên thiết bị, toạ độ vật lý,
màn Primary, có cảm ứng không).

QScreen.name() trong Qt 6 là tên model màn, không phải "\\\\.\\DISPLAYn"; nhưng
QScreen.nativeInterface().handle() trả thẳng HMONITOR nên hỏi Windows được ngay.

Cảm ứng: GetPointerDevices() cho biết mỗi thiết bị cảm ứng đang gắn với HMONITOR nào. Windows
chỉ biết đúng sau khi chạy "Tablet PC Settings → Setup"; chưa chạy thì mọi cảm ứng bị gán vào
màn Primary (xem HUONG_DAN_TEST.md).
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes as w
from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication, QScreen

from desktop.layout import Monitor

logger = logging.getLogger("pentasync.app")

POINTER_DEVICE_TYPE_TOUCH = 3
MONITORINFOF_PRIMARY = 1


class _POINTER_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("displayOrientation", w.DWORD),
        ("device", w.HANDLE),
        ("pointerDeviceType", w.DWORD),
        ("monitor", w.HMONITOR),
        ("startingCursorId", w.ULONG),
        ("maxActiveContacts", w.USHORT),
        ("productString", w.WCHAR * 520),
    ]


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("rcMonitor", w.RECT),
        ("rcWork", w.RECT),
        ("dwFlags", w.DWORD),
        ("szDevice", w.WCHAR * 32),
    ]


class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("DeviceName", w.WCHAR * 32),
        ("DeviceString", w.WCHAR * 128),
        ("StateFlags", w.DWORD),
        ("DeviceID", w.WCHAR * 128),
        ("DeviceKey", w.WCHAR * 128),
    ]


@dataclass(frozen=True)
class ScreenEntry:
    monitor: Monitor
    screen: QScreen
    scale_percent: int
    gpu: str = ""
    handle: int = 0  # HMONITOR — so với màn mà Windows thật sự đặt cửa sổ vào

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """Khung màn theo pixel thật (x, y, rộng, cao)."""
        m = self.monitor
        return m.x, m.y, m.width, m.height

    def describe(self) -> dict:
        """Thông tin cho lớp "Nhận diện màn" và màn quản lý."""
        m = self.monitor
        return {
            "device": m.key,
            "width": m.width,
            "height": m.height,
            "scale": self.scale_percent,
            "touch": m.touch,
            "primary": m.primary,
            "gpu": self.gpu,
        }


def _gpu_names() -> dict[str, str]:
    """"\\\\.\\DISPLAYn" → tên card đồ hoạ đang xuất hình ra màn đó. Máy test có cả card rời lẫn
    đồ hoạ tích hợp — biết màn nào chạy card nào giúp dò lỗi hình/hiệu năng tại chỗ."""
    if sys.platform != "win32":
        return {}
    names = {}
    device = _DISPLAY_DEVICEW()
    device.cb = ctypes.sizeof(_DISPLAY_DEVICEW)
    index = 0
    while ctypes.windll.user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
        names[device.DeviceName] = " ".join(
            device.DeviceString.replace("(TM)", "").replace("(R)", "").split()
        )
        index += 1
    return names


def touch_devices() -> list[int]:
    """Mỗi thiết bị cảm ứng Windows đang thấy → HMONITOR nó được gán (0 = chưa gán màn nào)."""
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    count = w.UINT(0)
    try:
        if not user32.GetPointerDevices(ctypes.byref(count), None) or not count.value:
            return []
        devices = (_POINTER_DEVICE_INFO * count.value)()
        if not user32.GetPointerDevices(ctypes.byref(count), devices):
            return []
    except (OSError, AttributeError):
        logger.exception("Không đọc được danh sách thiết bị cảm ứng")
        return []
    return [
        int(d.monitor or 0)
        for d in devices[: count.value]
        if d.pointerDeviceType == POINTER_DEVICE_TYPE_TOUCH
    ]


def touch_problem(device_monitors: list[int], entries: list[ScreenEntry]) -> str | None:
    """Dấu hiệu cảm ứng chưa được gán đúng màn (chưa chạy Tablet PC Settings → Setup).

    Chỉ là cảnh báo để người vận hành kiểm tra: một màn cảm ứng đôi khi khai báo 2 thiết bị.
    """
    if not device_monitors:
        return None
    known = {e.handle for e in entries}
    unmapped = sum(1 for h in device_monitors if h not in known)
    if unmapped:
        return (f"{unmapped}/{len(device_monitors)} thiết bị cảm ứng chưa gắn với màn nào đang dùng — "
                "chạy Control Panel → Tablet PC Settings → Setup")
    screens = set(device_monitors)
    if len(screens) < len(device_monitors):
        return (f"{len(device_monitors)} thiết bị cảm ứng nhưng chỉ gắn vào {len(screens)} màn — nếu có nhiều "
                "màn cảm ứng thì chạy Control Panel → Tablet PC Settings → Setup")
    primary = {e.handle for e in entries if e.monitor.primary}
    if len(entries) > 1 and screens <= primary:
        return ("Mọi cảm ứng đang gắn vào màn chính của Windows — nếu màn chính không phải màn cảm ứng "
                "thì chạy Control Panel → Tablet PC Settings → Setup")
    return None


def _win32_monitor(handle: int):
    info = _MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
    if not ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(handle), ctypes.byref(info)):
        return None
    return info


def _native_handle(screen: QScreen) -> int | None:
    try:
        native = screen.nativeInterface()
        return int(native.handle()) if native is not None else None
    except (AttributeError, TypeError, RuntimeError):
        return None


def read_screens(app: QGuiApplication) -> list[ScreenEntry]:
    touch_handles = set(touch_devices())
    gpus = _gpu_names()
    primary = app.primaryScreen()
    entries = []
    for index, screen in enumerate(app.screens()):
        scale = round(screen.devicePixelRatio() * 100)
        handle = _native_handle(screen) if sys.platform == "win32" else None
        info = _win32_monitor(handle) if handle else None
        if info is not None:
            r = info.rcMonitor
            monitor = Monitor(
                key=info.szDevice,
                x=r.left,
                y=r.top,
                width=r.right - r.left,
                height=r.bottom - r.top,
                primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                touch=handle in touch_handles,
            )
        else:
            # Không hỏi được Windows (máy khác hệ điều hành / lỗi hiếm): dùng số liệu của Qt.
            g = screen.geometry()
            monitor = Monitor(
                key=f"{screen.name()}#{index}",
                x=g.x(),
                y=g.y(),
                width=round(g.width() * screen.devicePixelRatio()),
                height=round(g.height() * screen.devicePixelRatio()),
                primary=screen is primary,
                touch=False,
            )
        entries.append(ScreenEntry(monitor=monitor, screen=screen, scale_percent=scale,
                                   gpu=gpus.get(monitor.key, ""), handle=int(handle or 0) if info else 0))
    return entries
