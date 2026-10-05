from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.logging_setup import get_logger

logger = get_logger()


class ResettableTimer:
    """Timer 1 lần bắn, có thể reset/hủy bất kỳ lúc nào. Chạy trên asyncio event loop
    của backend — không dùng threading.Timer để tránh phải đồng bộ giữa thread và
    event loop (nguồn race condition từng gặp trong video_sleep.py cũ với state_lock).

    on_fire không được mutate state trực tiếp — nó phải phát 1 Command vào hàng đợi
    trung tâm của ClusterController, giữ đúng nguyên tắc single-writer.
    """

    def __init__(self, on_fire: Callable[[], Awaitable[None]]):
        self._on_fire = on_fire
        self._task: asyncio.Task | None = None

    def reset(self, delay_sec: float) -> None:
        self.cancel()
        self._task = asyncio.create_task(self._run(delay_sec))

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    @property
    def is_active(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self, delay_sec: float) -> None:
        try:
            await asyncio.sleep(delay_sec)
        except asyncio.CancelledError:
            return
        try:
            await self._on_fire()
        except Exception:
            logger.exception("Loi khong bat duoc trong ResettableTimer.on_fire()")
