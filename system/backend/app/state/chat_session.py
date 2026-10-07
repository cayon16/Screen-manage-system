from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from app.commands import (
    AiReplyFailedCommand,
    AiReplyReadyCommand,
    Command,
    ErrorCleanupFiredCommand,
    Tier1CleanupFiredCommand,
    Tier1WarningFiredCommand,
)
from app.config import (
    ERROR_CLEANUP_SEC,
    SUPERDOC_HISTORY_LIMIT,
    TIER1_CLEANUP_SEC,
    TIER1_WARNING_SEC,
)
from app.db import ChatStore
from app.logging_setup import get_logger
from app.state.timers import ResettableTimer
from app.superdoc.base import ChatContext, SuperdocError, Turn
from app.superdoc.manager import AiLease

logger = get_logger()

SubmitFn = Callable[[Command], Awaitable[None]]


class ChatSession:
    """1 phien chat cua DUNG 1 man hinh. Man 2 va man 4 co the co 2 phien chay song song va
    hoan toan khong biet gi ve nhau — day chinh la "su doc lap tuyet doi" trong dac ta.

    Nguyen tac giu single-writer: session nay KHONG tu sua state cua man hinh. Timer het han
    hay AI tra loi xong deu chi day 1 Command vao hang doi trung tam; ClusterController moi la
    noi duy nhat doi state va gui message ra ngoai.
    """

    def __init__(
        self,
        session_id: str,
        screen_id: int,
        ai: AiLease,
        store: ChatStore,
        submit: SubmitFn,
    ):
        self.session_id = session_id
        self.screen_id = screen_id
        self.started_at = time.time()
        self.history: list[Turn] = []
        self.waiting_for_ai = False
        self.in_error = False

        # AI duoc "muon" luc mo phien va giu den khi dong: doi AI giua chung khong lam doi AI cua
        # phien dang do (chatbot noi bo co the giu phien phia no).
        self._ai = ai
        self._ai_context = ChatContext(session_id, screen_id, ai.system_prompt)
        self._store = store
        self._submit = submit

        self._warning_timer = ResettableTimer(self._fire_warning)
        self._cleanup_timer = ResettableTimer(self._fire_cleanup)
        self._error_timer = ResettableTimer(self._fire_error_cleanup)
        self._ai_task: asyncio.Task | None = None

    # ---------- vong doi ----------

    async def start(self) -> None:
        await self._store.open_session(self.session_id, self.screen_id)
        self.mark_activity()

    def cancel_all_timers(self) -> None:
        self._warning_timer.cancel()
        self._cleanup_timer.cancel()
        self._error_timer.cancel()

    async def close(self, reason: str) -> None:
        """Don dep tuyet doi: huy lenh AI dang chay -> tat moi timer -> xoa lich su trong bo nho
        -> dong ban ghi phien trong database. Goi 2 lan cung an toan."""
        self.cancel_ai_task()
        self.cancel_all_timers()

        # Bao cho AI biet doan chat ket thuc (chatbot noi bo co the giu phien phia no; cac AI cong
        # khai la no-op). Loi o day khong duoc lam hong viec don dep.
        try:
            await self._ai.provider.end_session(self._ai_context, reason)
        except Exception:
            logger.exception("Bao ket thuc phien cho Superdoc that bai (man %s)", self.screen_id)
        finally:
            self._ai.release()

        # Xoa lich su trong BO NHO de nguoi ke tiep khong doc duoc cuoc tro chuyen truoc do.
        # Ban ghi trong database van giu — do la yeu cau "luu toan bo lich su tro chuyen".
        self.history.clear()
        self.waiting_for_ai = False
        await self._store.close_session(self.session_id, reason)

    # ---------- Tier-1 ----------

    def mark_activity(self) -> None:
        """Co dau hieu nguoi dung con o day -> quay lai dem tu dau tang 1.

        Trong luc dang cho AI thi khong dem: cho AI tra loi khong phai la nguoi dung bo di.
        Dat guard ngay tai day de moi noi goi mark_activity() deu dung, khong phai nho kiem tra."""
        if self.waiting_for_ai:
            return
        self._cleanup_timer.cancel()
        # Cung phai huy dong ho don dep sau loi: dong ho do sinh ra de don man hinh dang treo
        # thong bao loi ma KHONG CO AI dung do. Nguoi dung vua cham man tuc la ho van o day —
        # neu de nguyen, phien chat cua ho bi dong giua chung sau ERROR_CLEANUP_SEC giay.
        # Tu day tro di Tier-1 lo viec don dep, dung nhu 1 phien binh thuong.
        self._error_timer.cancel()
        self._warning_timer.reset(TIER1_WARNING_SEC)

    def pause_idle_countdown(self) -> None:
        """Trong luc AI dang nghi, im lang KHONG phai la nguoi dung bo di — dung dem nguoc."""
        self._warning_timer.cancel()
        self._cleanup_timer.cancel()

    def start_cleanup_countdown(self) -> None:
        """Da hien canh bao "ban con o day khong?" — cho them TIER1_CLEANUP_SEC roi tu dong dep."""
        self._cleanup_timer.reset(TIER1_CLEANUP_SEC)

    # ---------- loi ----------

    def enter_error(self) -> None:
        self.in_error = True
        self.pause_idle_countdown()
        self._error_timer.reset(ERROR_CLEANUP_SEC)

    def clear_error(self) -> None:
        self.in_error = False
        self._error_timer.cancel()

    # ---------- goi AI ----------

    def ask(self, text: str) -> None:
        """Ghi cau hoi vao lich su roi goi AI o background. Tra ve ngay — hang doi command
        khong duoc phep dung cho AI, neu khong 1 phien cham se lam dong toan bo he thong."""
        self.clear_error()
        self.history.append(Turn(role="user", text=text))
        self.waiting_for_ai = True
        self.pause_idle_countdown()

        self.cancel_ai_task()
        self._ai_task = asyncio.create_task(self._run_ai())

    def cancel_ai_task(self) -> None:
        if self._ai_task is not None and not self._ai_task.done():
            self._ai_task.cancel()
        self._ai_task = None

    def record_reply(self, text: str) -> None:
        self.history.append(Turn(role="assistant", text=text))
        self.waiting_for_ai = False

    async def persist(self, role: str, text: str) -> None:
        await self._store.add_message(self.session_id, role, text)

    async def _run_ai(self) -> None:
        # Cat bot lich su cu: payload gui AI phai co tran, khong duoc phinh mai theo do dai phien.
        context = self.history[-SUPERDOC_HISTORY_LIMIT:]
        try:
            text = await asyncio.wait_for(
                self._ai.provider.reply(context, self._ai_context), timeout=self._ai.timeout_sec
            )
        except asyncio.CancelledError:
            # Phien bi dong hoac nguoi dung gui cau khac de len — khong bao loi ra man hinh.
            raise
        except asyncio.TimeoutError:
            # wait_for tu huy cuoc goi nen provider khong biet minh da cham: bao lai de dem vao tinh trang.
            self._ai.note_timeout()
            await self._submit(
                AiReplyFailedCommand(
                    screen_id=self.screen_id,
                    session_id=self.session_id,
                    code="ai_timeout",
                    message="Superdoc phản hồi quá lâu. Bạn thử hỏi lại giúp tôi nhé.",
                )
            )
            return
        except SuperdocError as exc:
            logger.warning("Superdoc that bai o man %s: %s", self.screen_id, exc)
            await self._submit(
                AiReplyFailedCommand(
                    screen_id=self.screen_id,
                    session_id=self.session_id,
                    code="ai_unavailable",
                    message="Hiện chưa kết nối được tới Superdoc. Bạn vui lòng thử lại sau ít phút.",
                )
            )
            return
        except Exception:
            logger.exception("Loi khong luong truoc khi goi Superdoc o man %s", self.screen_id)
            await self._submit(
                AiReplyFailedCommand(
                    screen_id=self.screen_id,
                    session_id=self.session_id,
                    code="ai_error",
                    message="Đã có lỗi khi xử lý câu hỏi. Bạn vui lòng thử lại.",
                )
            )
            return

        await self._submit(
            AiReplyReadyCommand(screen_id=self.screen_id, session_id=self.session_id, text=text)
        )

    # ---------- callback cua timer (chi day command, khong sua state) ----------

    async def _fire_warning(self) -> None:
        await self._submit(Tier1WarningFiredCommand(screen_id=self.screen_id, session_id=self.session_id))

    async def _fire_cleanup(self) -> None:
        await self._submit(Tier1CleanupFiredCommand(screen_id=self.screen_id, session_id=self.session_id))

    async def _fire_error_cleanup(self) -> None:
        await self._submit(ErrorCleanupFiredCommand(screen_id=self.screen_id, session_id=self.session_id))
