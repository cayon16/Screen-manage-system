from __future__ import annotations

import asyncio
import ctypes
import sys
from typing import Awaitable, Callable

from app.commands import Command, HostActivityCommand
from app.config import HOST_ACTIVITY_POLL_SEC
from app.logging_setup import get_logger

logger = get_logger()

SubmitFn = Callable[[Command], Awaitable[None]]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def last_input_tick() -> int | None:
    """So mili-giay (tinh tu luc may khoi dong) cua lan cuoi CO INPUT chuot/ban phim tren may chu.

    Tra ve None neu he dieu hanh khong ho tro — khi do tinh nang nay tu tat, phan con lai cua
    he thong khong bi anh huong.
    """
    if sys.platform != "win32":
        return None
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    return int(info.dwTime)


class HostActivityMonitor:
    """Dac ta yeu cau: he thong chi duoc ngu khi "khong co ai tuong tac o man 2/4 VA o may chu
    khong co ai thao tac gi". Cham man hinh thi da co WebSocket bao ve; con thao tac chuot/phim
    truc tiep tren may chu thi trinh duyet khong he biet — nen phai hoi thang Windows.

    Cach lam: hoi GetLastInputInfo moi HOST_ACTIVITY_POLL_SEC giay, chi khi moc thoi gian doi
    moi day 1 command (khong day lien tuc lam nghen hang doi).
    """

    def __init__(self, submit: SubmitFn, poll_sec: float = HOST_ACTIVITY_POLL_SEC):
        self._submit = submit
        self._poll_sec = poll_sec

    async def run(self) -> None:
        last_seen = last_input_tick()
        if last_seen is None:
            logger.info("Khong doc duoc input cua may chu tren nen tang %s — bo qua tinh nang nay", sys.platform)
            return

        logger.info("Theo doi thao tac tren may chu moi %.1fs", self._poll_sec)
        while True:
            await asyncio.sleep(self._poll_sec)
            tick = last_input_tick()
            if tick is None or tick == last_seen:
                continue
            last_seen = tick
            await self._submit(HostActivityCommand())
