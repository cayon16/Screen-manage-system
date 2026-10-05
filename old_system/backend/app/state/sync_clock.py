from __future__ import annotations

import time

# Dong ho chung cho che do cho.
#
# Van de: dac ta cam "5 man 5 video doc lap" — 5 man phai ghep thanh 1 khung hinh lien mach.
# Cach giai: khong truyen frame, khong dong bo tung khung hinh. Server chi cap 1 moc thoi gian
# t0 dung chung; moi man tu tinh video phai dang o giay thu may:
#
#     target = (now_server - t0) mod video.duration
#
# roi tu keo currentTime cua no ve dung moc do. Vi ca 5 man dung CHUNG 1 cong thuc va CHUNG 1
# moc thoi gian, chung khong the troi khoi nhau.
#
# t0 lay o thoi diem nao cung dung, mien la CA 5 MAN dung chung 1 gia tri. Lay luon moc khoi
# dong tien trinh backend.
_T0_EPOCH = time.time()


def snapshot() -> dict[str, float]:
    """Du lieu de client tu tinh do lech dong ho cua no so voi server.

    Hien tai ca 5 trinh duyet chay tren cung 1 may nen do lech ~0, nhung giu san co che nay de
    khi scale len nhieu may (theo ke hoach cua khach) khong phai sua lai frontend.
    """
    return {
        "t0": _T0_EPOCH,
        "server_now": time.time(),
    }
