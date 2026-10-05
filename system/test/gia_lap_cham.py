"""Thiết bị cảm ứng ảo của Windows (`InjectTouchInput`) — chạm THẬT mà không cần màn cảm ứng.

Chạy như một tiến trình riêng, nhận lệnh qua đầu vào chuẩn (mỗi dòng 1 lệnh):

    cham X Y MS       chạm tại pixel vật lý (X, Y), giữ MS mili giây rồi nhả
    phim ctrl+shift+q bấm tổ hợp phím thật
    thiet_bi          in danh sách thiết bị cảm ứng Windows đang thấy
    thoat

Mỗi tiến trình = 1 thiết bị cảm ứng. Muốn giả lập 2 màn cảm ứng thì chạy 2 tiến trình
(dùng lớp `MayCham` trong `chung.py`), vì 2 màn thật cũng là 2 thiết bị riêng — Windows gộp
nhiều ngón của CÙNG một thiết bị vào một "khung" chạm, không giống 2 người dùng 2 màn.
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes as w

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2: toạ độ = pixel thật

PT_TOUCH = 2
POINTER_FLAG_INRANGE = 0x2
POINTER_FLAG_INCONTACT = 0x4
POINTER_FLAG_DOWN = 0x10000
POINTER_FLAG_UPDATE = 0x20000
POINTER_FLAG_UP = 0x40000
TOUCH_MASK_ALL = 0x1 | 0x2 | 0x4  # vùng tiếp xúc, hướng, lực
TOUCH_FEEDBACK_DEFAULT = 0x1
KEYEVENTF_KEYUP = 2
PHIM_DAC_BIET = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12}


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", w.DWORD), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
        ("pointerFlags", ctypes.c_uint32), ("sourceDevice", w.HANDLE), ("hwndTarget", w.HWND),
        ("ptPixelLocation", w.POINT), ("ptHimetricLocation", w.POINT),
        ("ptPixelLocationRaw", w.POINT), ("ptHimetricLocationRaw", w.POINT),
        ("dwTime", w.DWORD), ("historyCount", ctypes.c_uint32), ("InputData", ctypes.c_int32),
        ("dwKeyStates", w.DWORD), ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32), ("touchMask", ctypes.c_uint32),
        ("rcContact", w.RECT), ("rcContactRaw", w.RECT), ("orientation", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32),
    ]


class POINTER_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("displayOrientation", w.DWORD), ("device", w.HANDLE), ("pointerDeviceType", w.DWORD),
        ("monitor", w.HMONITOR), ("startingCursorId", w.ULONG), ("maxActiveContacts", w.USHORT),
        ("productString", w.WCHAR * 520),
    ]


def _ngon(x: int, y: int, co: int) -> POINTER_TOUCH_INFO:
    c = POINTER_TOUCH_INFO()
    c.pointerInfo.pointerType = PT_TOUCH
    c.pointerInfo.pointerId = 0
    c.pointerInfo.ptPixelLocation = w.POINT(x, y)
    c.pointerInfo.pointerFlags = co
    c.touchMask = TOUCH_MASK_ALL
    c.rcContact = w.RECT(x - 4, y - 4, x + 4, y + 4)
    c.orientation = 90
    c.pressure = 32000
    return c


def _bom(ngon: POINTER_TOUCH_INFO) -> bool:
    arr = (POINTER_TOUCH_INFO * 1)(ngon)
    if not user32.InjectTouchInput(1, arr):
        print("LOI_BOM", ctypes.get_last_error(), flush=True)
        return False
    return True


def cham(x: int, y: int, giu_ms: int) -> None:
    xuong = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
    giu = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
    _bom(_ngon(x, y, xuong))
    het = time.time() + giu_ms / 1000
    while time.time() < het:
        # Windows huỷ lần chạm nếu không được cập nhật liên tục khi đang giữ tay.
        time.sleep(0.03)
        _bom(_ngon(x, y, giu))
    _bom(_ngon(x, y, POINTER_FLAG_UP))


def phim(to_hop: str) -> None:
    ma = [PHIM_DAC_BIET.get(k, ord(k.upper()) if len(k) == 1 else 0) for k in to_hop.split("+")]
    for m in ma:
        user32.keybd_event(m, 0, 0, 0)
    time.sleep(0.05)
    for m in reversed(ma):
        user32.keybd_event(m, 0, KEYEVENTF_KEYUP, 0)


def thiet_bi() -> list[tuple[int, int, str]]:
    so = w.UINT(0)
    user32.GetPointerDevices(ctypes.byref(so), None)
    arr = (POINTER_DEVICE_INFO * max(so.value, 1))()
    user32.GetPointerDevices(ctypes.byref(so), arr)
    return [(d.pointerDeviceType, int(d.monitor or 0), d.productString[:40]) for d in arr[: so.value]]


def main() -> int:
    ok = user32.InitializeTouchInjection(10, TOUCH_FEEDBACK_DEFAULT)
    print("SAN_SANG", bool(ok), flush=True)
    for dong in sys.stdin:
        phan = dong.split()
        if not phan:
            continue
        lenh = phan[0]
        try:
            if lenh == "cham":
                cham(int(phan[1]), int(phan[2]), int(phan[3]))
            elif lenh == "phim":
                phim(phan[1])
            elif lenh == "thiet_bi":
                print("THIET_BI", thiet_bi(), flush=True)
            elif lenh == "thoat":
                break
            print("XONG", lenh, flush=True)
        except Exception as exc:
            print("LOI", lenh, exc, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
