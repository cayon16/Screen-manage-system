from __future__ import annotations

import asyncio
import time
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Awaitable, Callable

from app.commands import (
    AdminCommand,
    AdminConnectedCommand,
    AiReplyFailedCommand,
    AiReplyReadyCommand,
    ChatMessageCommand,
    ClientConnectedCommand,
    ClientDisconnectedCommand,
    Command,
    ErrorCleanupFiredCommand,
    HostActivityCommand,
    LayoutCommand,
    SelectSlideCommand,
    SlicesReadyCommand,
    Tier1AckCommand,
    Tier1CleanupFiredCommand,
    Tier1WarningFiredCommand,
    Tier2FiredCommand,
    TouchCommand,
)
from app.config import (
    ALL_SCREENS,
    CHAT_SCREEN,
    CONTROL_SCREEN,
    SLIDE_SCREENS,
    TIER1_CLEANUP_SEC,
    TIER2_CLUSTER_IDLE_SEC,
    TOUCH_SCREENS,
)
from app.db import ChatStore
from app.logging_setup import get_logger
from app.schemas import (
    AdminSnapshotMsg,
    ChatMessageAckMsg,
    ConfirmPromptMsg,
    ErrorMsg,
    ServerMessage,
    SessionClosedMsg,
    StateUpdateMsg,
)
from app.state import sync_clock
from app.state.chat_session import ChatSession
from app.state.layout import ClusterLayout
from app.state.screen_fsm import (
    EFFECT_ACTIVATE_BAND,
    EFFECT_CLOSE_CHAT_SESSION,
    EFFECT_OPEN_CHAT_SESSION,
    ROLE_BY_SCREEN,
    ScreenEvent,
    ScreenState,
    transition,
)
from app.state.slide_band import SlideBand
from app.state.timers import ResettableTimer
from app.superdoc.base import SuperdocProvider
from app.superdoc.factory import build_provider

if TYPE_CHECKING:
    from app.state.video_slicer import VideoSlicer

logger = get_logger()

# Anh xa "target" nguoi dung cham (tu TouchEventMsg qua WebSocket) sang ScreenEvent cua FSM thuan.
_TARGET_TO_EVENT: dict[str, ScreenEvent] = {
    "generic_wake": ScreenEvent.TOUCH_OWN,
    "chat_button": ScreenEvent.TOUCH_OWN,
    "menu_option_info": ScreenEvent.MENU_SELECT_INFO,
    "menu_option_chat": ScreenEvent.MENU_SELECT_CHAT,
    "menu_back": ScreenEvent.MENU_BACK,
    "exit_chat": ScreenEvent.CHAT_EXIT,
    "confirm_yes": ScreenEvent.CONFIRM_YES,
    "confirm_no": ScreenEvent.CONFIRM_NO,
}

_VIEW_BY_STATE: dict[ScreenState, str] = {
    ScreenState.STANDBY: "standby",
    ScreenState.MENU: "menu",
    ScreenState.SLIDE_CONTROL: "slide_control",
    ScreenState.PROMPT_CHAT_BUTTON: "prompt_chat",
    ScreenState.SLIDE_MEMBER: "slide",
    ScreenState.CHAT: "chat",
    ScreenState.CHAT_CONFIRM_SWITCH: "chat",
}

VIEW_BLACKOUT = "blackout"

# Ly do dong phien, suy ra tu chinh su kien gay ra viec dong — de client va ban ghi database
# luon khop nhau ve nguyen nhan.
_CLOSE_REASON_BY_EVENT: dict[ScreenEvent, str] = {
    ScreenEvent.CHAT_EXIT: "user_exit",
    ScreenEvent.TIER1_TIMEOUT: "tier1_timeout",
    ScreenEvent.ERROR_TIMEOUT: "error_timeout",
    ScreenEvent.CONFIRM_YES: "mode_switch",
    ScreenEvent.CLUSTER_RESET: "cluster_reset",
}

MODE_SWITCH_CONFIRM_MESSAGE = (
    "Chuyển sang xem Thông tin bệnh viện sẽ kết thúc đoạn chat hiện tại. Bạn có đồng ý không?"
)
TIER1_WARNING_MESSAGE = "Bạn còn muốn tiếp tục trò chuyện không?"

SendFn = Callable[[int, ServerMessage], Awaitable[None]]
SendAdminFn = Callable[[AdminSnapshotMsg], Awaitable[None]]


def _other_touch_screen(screen_id: int) -> int:
    return CHAT_SCREEN if screen_id == CONTROL_SCREEN else CONTROL_SCREEN


class ClusterController:
    """Single-writer orchestrator: moi mutation state di qua 1 hang doi Command duy nhat,
    xu ly tuan tu trong run(). Khong co code path nao khac duoc phep sua state -> khong can lock."""

    def __init__(
        self,
        send: SendFn,
        *,
        provider: SuperdocProvider | None = None,
        store: ChatStore | None = None,
        slide_band: SlideBand | None = None,
        send_admin: SendAdminFn | None = None,
        slicer: "VideoSlicer | None" = None,
    ):
        self._send = send
        self._send_admin = send_admin
        self._slicer = slicer
        self._provider = provider if provider is not None else build_provider()
        self._store = store if store is not None else ChatStore()
        self._slide_band = slide_band if slide_band is not None else SlideBand.load()

        self._queue: asyncio.Queue[Command] = asyncio.Queue()
        self._states: dict[int, ScreenState] = {sid: ScreenState.STANDBY for sid in ALL_SCREENS}
        self._chat_sessions: dict[int, ChatSession] = {}
        self._tier2_timer = ResettableTimer(self._on_tier2_fired)
        self._running = False

        self._layout = ClusterLayout.default()
        # Man den (khach bam "Tat han" tren man quan ly): moi man den thui, bo qua moi thao tac
        # cham va thao tac may chu, cho toi khi man quan ly bat lai.
        self._blackout = False
        # vai tro -> dinh danh ket noi dang song (xem ClientConnectedCommand.conn_id)
        self._connections: dict[int, str] = {}

        self._started_at = time.time()
        self._admin_dirty = False
        self._chats_today = 0
        self._avg_chat_seconds: float | None = None
        self._ai_error_day = date.today()
        self._ai_errors_today = 0

    # ---------- public API ----------

    async def submit(self, command: Command) -> None:
        await self._queue.put(command)

    async def run(self) -> None:
        await self._store.init()
        await self._refresh_stats()
        self._running = True
        while self._running:
            command = await self._queue.get()
            try:
                await self._handle(command)
            except Exception:
                logger.exception("Loi khi xu ly command %r", command)
            finally:
                self._queue.task_done()

    def stop(self) -> None:
        self._running = False
        self._tier2_timer.cancel()
        for session in self._chat_sessions.values():
            session.cancel_ai_task()
            session.cancel_all_timers()

    def state_of(self, screen_id: int) -> ScreenState:
        return self._states[screen_id]

    def session_of(self, screen_id: int) -> ChatSession | None:
        return self._chat_sessions.get(screen_id)

    @property
    def layout(self) -> ClusterLayout:
        return self._layout

    @property
    def blackout(self) -> bool:
        return self._blackout

    async def wait_idle(self) -> None:
        """Cho toi khi hang doi command da xu ly het — dung cho test, khong dung trong production."""
        await self._queue.join()

    # ---------- command dispatch ----------

    async def _handle(self, command: Command) -> None:
        if isinstance(command, TouchCommand):
            await self._handle_touch(command)
        elif isinstance(command, ChatMessageCommand):
            await self._handle_chat_message(command)
        elif isinstance(command, AiReplyReadyCommand):
            await self._handle_ai_reply(command)
        elif isinstance(command, AiReplyFailedCommand):
            await self._handle_ai_failure(command)
        elif isinstance(command, SelectSlideCommand):
            await self._handle_select_slide(command)
        elif isinstance(command, HostActivityCommand):
            await self._handle_host_activity()
        elif isinstance(command, ClientConnectedCommand):
            self._connections[command.screen_id] = command.conn_id
            self._admin_dirty = True
            await self._send_state(command.screen_id)
        elif isinstance(command, ClientDisconnectedCommand):
            # Reload trang / rot mang chop nhoang KHONG duoc giet phien chat: nguoi dung van dung
            # do, man hinh tu ket noi lai sau 1 giay. Neu ho bo di that thi Tier-1 se don.
            if self._connections.get(command.screen_id) == command.conn_id:
                del self._connections[command.screen_id]
                self._admin_dirty = True
            logger.info("Man %s mat ket noi WebSocket", command.screen_id)
        elif isinstance(command, Tier2FiredCommand):
            await self._handle_tier2_fired()
        elif isinstance(command, Tier1AckCommand):
            session = self._session_for(command.screen_id, command.session_id)
            if session is not None:
                session.mark_activity()
        elif isinstance(command, Tier1WarningFiredCommand):
            await self._handle_tier1_warning(command)
        elif isinstance(command, Tier1CleanupFiredCommand):
            if self._session_for(command.screen_id, command.session_id) is not None:
                await self._apply_event(command.screen_id, ScreenEvent.TIER1_TIMEOUT)
        elif isinstance(command, ErrorCleanupFiredCommand):
            if self._session_for(command.screen_id, command.session_id) is not None:
                await self._apply_event(command.screen_id, ScreenEvent.ERROR_TIMEOUT)
        elif isinstance(command, LayoutCommand):
            await self._handle_layout(command.layout)
        elif isinstance(command, AdminCommand):
            await self._handle_admin(command)
        elif isinstance(command, AdminConnectedCommand):
            self._admin_dirty = True
        elif isinstance(command, SlicesReadyCommand):
            await self._handle_slices_ready(command.wall_count)
        else:
            logger.warning("Command khong xac dinh: %r", command)

        # Moi command sinh ra toi da 1 anh chup cho man quan ly, du no lam doi state bao nhieu
        # man (vd danh thuc ca cum doi 5 man cung luc).
        if self._admin_dirty:
            await self._publish_admin()

    # ---------- cham man hinh ----------

    async def _handle_touch(self, command: TouchCommand) -> None:
        if self._blackout:
            return
        if not self._layout.is_active(command.screen_id):
            # Cua so cua 1 man vua bi rut ra van con gui kip vai lan cham — bo qua.
            logger.warning("Man %s khong con trong bo cuc — bo qua thao tac cham", command.screen_id)
            return

        event = _TARGET_TO_EVENT.get(command.target)
        if event is None:
            logger.warning("Touch target khong nhan dien duoc: %s", command.target)
            return

        # Cham vao bat cu dau trong khi dang chat = nguoi dung van con day -> hoan Tier-1.
        session = self._chat_sessions.get(command.screen_id)
        if session is not None:
            session.mark_activity()

        was_asleep = self._all_standby()
        await self._apply_event(command.screen_id, event)

        # Cham Man 2 hoac Man 4 tu Standby -> danh thuc CA HAI cung luc (neu man kia co that).
        if command.screen_id in TOUCH_SCREENS and event is ScreenEvent.TOUCH_OWN:
            other = _other_touch_screen(command.screen_id)
            if self._layout.is_active(other):
                await self._apply_event(other, ScreenEvent.WAKE_PAIR)

        if was_asleep:
            await self._activate_band()

        # Bat ky touch_event nao tu Man 2/4 deu reset dem nguoc Tier-2, du FSM co doi state hay khong.
        if command.screen_id in TOUCH_SCREENS:
            self._refresh_tier2_timer()

    async def _handle_host_activity(self) -> None:
        """Co nguoi dung chuot/ban phim tren may chu — tinh nhu 1 tuong tac that: danh thuc
        neu dang ngu, va lui thoi diem ngu neu dang thuc."""
        if self._blackout:
            return
        if self._all_standby():
            for sid in TOUCH_SCREENS:
                if self._layout.is_active(sid):
                    await self._apply_event(sid, ScreenEvent.WAKE_PAIR)
            await self._activate_band()
        self._refresh_tier2_timer()

    def _all_standby(self) -> bool:
        return all(self._states[role] is ScreenState.STANDBY for role in self._layout.roles)

    async def _activate_band(self, origin: int | None = None) -> None:
        """Bat dai slide tren cac man chieu slide dang co.

        descryption.txt muc 2: thoat Standby thi "ca 5 man deu quay ve chuc nang von co cua no"
        — chuc nang von co cua man 1/3/5 la trinh chieu, nen chung phai len slide ngay khi he
        thong thuc day, khong cho toi luc co nguoi bam "Thong tin benh vien".

        Man 2 va man 4 bo qua BAND_ACTIVATE o moi state cua chung (xem screen_fsm.py) nen goi ham
        nay khong bao gio lam gian doan menu hay phien chat dang mo.
        """
        for screen_id in self._layout.roles:
            if screen_id != origin:
                await self._apply_event(screen_id, ScreenEvent.BAND_ACTIVATE)

    async def _wake_role(self, role: int) -> None:
        """Dua 1 man vua xuat hien vao dung trang thai "dang thuc" nhu cac man khac.
        FSM tu bo qua su kien khong ap dung cho vai tro do."""
        await self._apply_event(role, ScreenEvent.WAKE_PAIR)
        await self._apply_event(role, ScreenEvent.BAND_ACTIVATE)

    # ---------- bo cuc man ----------

    async def _handle_layout(self, layout: ClusterLayout) -> None:
        old = self._layout
        was_awake = not self._all_standby()
        self._layout = layout
        self._admin_dirty = True
        logger.info("Bo cuc man moi: %s", layout.as_dict())

        for role in old.roles:
            if not layout.is_active(role):
                # Man bi rut ra (hoac tat nguon). Phien chat cua no khong con ai thay nua.
                await self._close_chat_session(role, "screen_removed")
                self._states[role] = ScreenState.STANDBY

        if was_awake and not self._blackout:
            for role in layout.roles:
                if not old.is_active(role):
                    await self._wake_role(role)

        if self._slicer is not None:
            self._slicer.ensure(layout.wall_count)

        # Vi tri tuong cua cac man co the da doi -> man dang cho phai nhan lai lat video moi.
        for role in layout.roles:
            await self._send_state(role)

    async def _handle_slices_ready(self, wall_count: int) -> None:
        if wall_count != self._layout.wall_count or self._blackout:
            return
        logger.info("Video cho da cat xong %s lat — cac man cho doi sang phat lat rieng", wall_count)
        for role in self._layout.roles:
            if self._states[role] is ScreenState.STANDBY:
                await self._send_state(role)

    # ---------- trinh chieu ----------

    async def _handle_select_slide(self, command: SelectSlideCommand) -> None:
        if self._blackout:
            return
        if self._states[command.screen_id] is not ScreenState.SLIDE_CONTROL:
            logger.warning(
                "Man %s gui select_slide nhung dang o state %s — bo qua",
                command.screen_id,
                self._states[command.screen_id],
            )
            return

        if await self._select_slide(command.slide_id):
            self._refresh_tier2_timer()

    async def _select_slide(self, slide_id: str) -> bool:
        target = self._slide_band.screen_of(slide_id)
        if target is None or not self._layout.is_active(target):
            logger.warning("slide_id khong ton tai hoac man cua no khong co: %s", slide_id)
            return False

        self._slide_band.select(slide_id)
        self._admin_dirty = True
        await self._send_state(target)
        # Bang dieu khien cua Man 2 (neu dang mo) phai to sang dung nut vua chon.
        if self._states[CONTROL_SCREEN] is ScreenState.SLIDE_CONTROL:
            await self._send_state(CONTROL_SCREEN)
        return True

    # ---------- chat ----------

    async def _handle_chat_message(self, command: ChatMessageCommand) -> None:
        session = self._session_for(command.screen_id, command.session_id)
        if session is None:
            return
        text = command.text.strip()
        if not text:
            return

        if session.waiting_for_ai:
            # O nhap bi khoa trong luc cho AI, nen truong hop nay chi xay ra voi client loi hoac
            # tin nhan den muon. Phai chan: nap them 1 luot "user" khi luot truoc chua co cau tra
            # loi se tao ra 2 luot user lien tiep trong lich su — Gemini that tu choi payload do.
            logger.warning("Man %s gui tin khi AI chua tra loi xong — bo qua", command.screen_id)
            return

        session.ask(text)
        await session.persist("user", text)
        self._refresh_tier2_timer()
        await self._send_state(command.screen_id)

    async def _handle_ai_reply(self, command: AiReplyReadyCommand) -> None:
        session = self._session_for(command.screen_id, command.session_id)
        if session is None:
            # Phien da dong trong luc AI dang nghi — bo cau tra loi di, khong gui ra man hinh
            # dang hien thi thu khac (co the la phien cua nguoi ke tiep).
            return

        session.record_reply(command.text)
        await session.persist("assistant", command.text)
        await self._send(
            command.screen_id,
            ChatMessageAckMsg(
                screen_id=command.screen_id,
                session_id=command.session_id,
                role="assistant",
                text=command.text,
            ),
        )
        session.mark_activity()
        await self._send_state(command.screen_id)

    async def _handle_ai_failure(self, command: AiReplyFailedCommand) -> None:
        session = self._session_for(command.screen_id, command.session_id)
        if session is None:
            return

        self._count_ai_error()
        session.waiting_for_ai = False
        session.enter_error()
        await self._send(
            command.screen_id,
            ErrorMsg(
                screen_id=command.screen_id,
                session_id=command.session_id,
                code=command.code,
                message=command.message,
            ),
        )
        await self._send_state(command.screen_id)

    def _session_for(self, screen_id: int, session_id: str) -> ChatSession | None:
        """Lay session neu VA CHI NEU session_id khop. Chan mot lop bug ca ho: message den muon
        (AI tra loi cham, tier1_ack bam tre) tac dong nham vao phien moi vua duoc mo."""
        session = self._chat_sessions.get(screen_id)
        if session is None or session.session_id != session_id:
            return None
        return session

    # ---------- ap dung su kien FSM ----------

    async def _apply_event(self, screen_id: int, event: ScreenEvent) -> None:
        role = ROLE_BY_SCREEN[screen_id]
        current = self._states[screen_id]
        result = transition(role, current, event)
        if not result.handled:
            return

        self._states[screen_id] = result.new_state

        if EFFECT_ACTIVATE_BAND in result.effects:
            await self._activate_band(origin=screen_id)

        if EFFECT_OPEN_CHAT_SESSION in result.effects:
            await self._open_chat_session(screen_id)

        if EFFECT_CLOSE_CHAT_SESSION in result.effects:
            await self._close_chat_session(screen_id, _CLOSE_REASON_BY_EVENT.get(event, "user_exit"))

        await self._send_state(screen_id)

        if result.new_state is ScreenState.CHAT_CONFIRM_SWITCH:
            await self._send(
                screen_id,
                # Khong dat timeout_sec: hop thoai nay cho nguoi dung chon dut khoat, khong tu
                # het han. (Neu ho bo di luon thi Tier-1 cua phien chat van don dep binh thuong.)
                ConfirmPromptMsg(
                    screen_id=screen_id,
                    kind="mode_switch",
                    message=MODE_SWITCH_CONFIRM_MESSAGE,
                ),
            )

    async def _open_chat_session(self, screen_id: int) -> None:
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            screen_id=screen_id,
            provider=self._provider,
            store=self._store,
            submit=self.submit,
        )
        self._chat_sessions[screen_id] = session
        await session.start()
        # Dang co phien chat mo -> khong duoc phep dua ca cum di ngu.
        self._refresh_tier2_timer()
        await self._refresh_stats()

    async def _close_chat_session(self, screen_id: int, reason: str) -> None:
        session = self._chat_sessions.pop(screen_id, None)
        if session is None:
            return
        await session.close(reason)
        await self._send(
            screen_id,
            SessionClosedMsg(screen_id=screen_id, session_id=session.session_id, reason=reason),
        )
        # Dong 1 phien chat la 1 trong cac dieu kien khoi dong lai dem nguoc Tier-2.
        self._refresh_tier2_timer()
        await self._refresh_stats()

    # ---------- gui state ra client ----------

    async def _send_state(self, screen_id: int) -> None:
        self._admin_dirty = True
        if self._blackout:
            await self._send(
                screen_id,
                StateUpdateMsg(
                    screen_id=screen_id,
                    state=self._states[screen_id].value,
                    view=VIEW_BLACKOUT,
                    data={},
                ),
            )
            return

        state = self._states[screen_id]
        await self._send(
            screen_id,
            StateUpdateMsg(
                screen_id=screen_id,
                state=state.value,
                view=_VIEW_BY_STATE[state],
                data=self._data_for(screen_id, state),
            ),
        )

    def _data_for(self, screen_id: int, state: ScreenState) -> dict:
        if state is ScreenState.STANDBY:
            return self._standby_data(screen_id)

        if state is ScreenState.SLIDE_MEMBER:
            slide = self._slide_band.current_slide(screen_id)
            return {"slide": slide.as_dict()} if slide is not None else {}

        if state is ScreenState.SLIDE_CONTROL:
            buttons = self._slide_band.buttons(self._layout.roles)
            # "current" giu lai cho giao dien web cu (xoa o giai doan 4); giao dien moi doc co
            # `current` ngay tren tung nut.
            current = {str(b["screen_id"]): b["slide_id"] for b in buttons if b["current"]}
            return {"buttons": buttons, "current": current}

        if state in (ScreenState.CHAT, ScreenState.CHAT_CONFIRM_SWITCH):
            session = self._chat_sessions.get(screen_id)
            if session is None:
                return {}
            return {
                "session_id": session.session_id,
                "waiting_for_ai": session.waiting_for_ai,
                "in_error": session.in_error,
            }

        return {}

    def _standby_data(self, screen_id: int) -> dict:
        """Man cho can biet: phat file nao, va cat phan nao cua file do.

        - Chua cat xong video (hoac chi co 1 man): phat ca video va tu dich khung de lay dung
          phan cua minh -> crop_index = vi tri tuong, crop_count = so man.
        - Da cat xong: moi man phat dung lat cua minh, khong can dich -> crop 0/1.
        Hai che do cho ra CUNG mot hinh; cat san chi de nhe may hon (xem TIEN_DO.md).
        """
        wall_index = self._layout.wall_index.get(screen_id, 0)
        wall_count = max(self._layout.wall_count, 1)
        data = {
            **sync_clock.snapshot(),
            # Giu ten cu cho giao dien web (xoa o giai doan 4).
            "screen_index": wall_index,
            "screen_count": wall_count,
        }
        if wall_count > 1 and self._slicer is not None and self._slicer.ready(wall_count):
            data.update(video_src=f"/standby-video/{wall_count}/{wall_index}", crop_index=0, crop_count=1)
        else:
            data.update(video_src="/standby-video", crop_index=wall_index, crop_count=wall_count)
        return data

    # ---------- Tier-2 (cluster) ----------

    def _tier2_gate_open(self) -> bool:
        """True khi khong con phien chat nao dang mo (phien dang loi cung la phien dang mo)."""
        return len(self._chat_sessions) == 0

    def _refresh_tier2_timer(self) -> None:
        if self._blackout:
            # Man den: he thong coi nhu dang tat, khong co gi de dem.
            self._tier2_timer.cancel()
            return
        if self._tier2_gate_open():
            self._tier2_timer.reset(TIER2_CLUSTER_IDLE_SEC)
        else:
            self._tier2_timer.cancel()

    async def _on_tier2_fired(self) -> None:
        await self.submit(Tier2FiredCommand())

    async def _handle_tier2_fired(self) -> None:
        for screen_id in ALL_SCREENS:
            await self._apply_event(screen_id, ScreenEvent.CLUSTER_RESET)
        # KHONG goi lai _refresh_tier2_timer() o day: sau khi ve Standby, timer phai dung yen
        # cho toi lan touch/dong-session that tiep theo, tranh vong lap tu khoi dong lai vo han.

    # ---------- Tier-1 (per-chat) ----------

    async def _handle_tier1_warning(self, command: Tier1WarningFiredCommand) -> None:
        session = self._session_for(command.screen_id, command.session_id)
        if session is None:
            return
        session.start_cleanup_countdown()
        await self._send(
            command.screen_id,
            ConfirmPromptMsg(
                screen_id=command.screen_id,
                kind="tier1_warning",
                session_id=command.session_id,
                message=TIER1_WARNING_MESSAGE,
                timeout_sec=TIER1_CLEANUP_SEC,
            ),
        )

    # ---------- man quan ly ----------

    async def _handle_admin(self, command: AdminCommand) -> None:
        action = command.action
        logger.info("Lenh tu man quan ly: %s %s", action, command.slide_id or "")
        self._admin_dirty = True

        if action == "refresh":
            await self._refresh_stats()
        elif action == "select_slide":
            if not self._blackout and command.slide_id:
                await self._select_slide(command.slide_id)
        elif action == "force_standby":
            if not self._blackout:
                await self._handle_tier2_fired()
                # Dong phien chat trong luc do da lam dem nguoc Tier-2 chay lai — ca cum da ngu
                # roi, khong con gi de dem.
                self._tier2_timer.cancel()
        elif action == "blackout_on":
            await self._enter_blackout()
        elif action == "blackout_off":
            await self._exit_blackout()
        elif action == "reset":
            await self._system_reset()
        else:
            logger.warning("Lenh quan ly khong ho tro: %s", action)

    async def _close_all_sessions(self, reason: str) -> None:
        for role in list(self._chat_sessions):
            await self._close_chat_session(role, reason)

    async def _enter_blackout(self) -> None:
        if self._blackout:
            return
        await self._close_all_sessions("blackout")
        self._blackout = True
        self._tier2_timer.cancel()
        for role in ALL_SCREENS:
            self._states[role] = ScreenState.STANDBY
        for role in self._layout.roles:
            await self._send_state(role)

    async def _exit_blackout(self) -> None:
        if not self._blackout:
            return
        self._blackout = False
        # Bat lai thi he thong o trang thai cho; ai cham vao thi thuc day nhu binh thuong.
        for role in self._layout.roles:
            await self._send_state(role)

    async def _system_reset(self) -> None:
        await self._close_all_sessions("system_reset")
        self._slide_band.reset()
        self._blackout = False
        for role in ALL_SCREENS:
            self._states[role] = ScreenState.STANDBY
        self._tier2_timer.cancel()
        for role in self._layout.roles:
            await self._send_state(role)

    # ---------- thong ke + anh chup cho man quan ly ----------

    def _count_ai_error(self) -> None:
        today = date.today()
        if today != self._ai_error_day:
            self._ai_error_day = today
            self._ai_errors_today = 0
        self._ai_errors_today += 1
        self._admin_dirty = True

    async def _refresh_stats(self) -> None:
        midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        self._chats_today, self._avg_chat_seconds = await self._store.stats_since(midnight)
        if date.today() != self._ai_error_day:
            self._ai_error_day = date.today()
            self._ai_errors_today = 0
        self._admin_dirty = True

    def admin_snapshot(self) -> AdminSnapshotMsg:
        screens = []
        for role in ALL_SCREENS:
            state = self._states[role]
            session = self._chat_sessions.get(role)
            slide = self._slide_band.current_slide(role) if role in SLIDE_SCREENS else None
            screens.append(
                {
                    "role": role,
                    "active": self._layout.is_active(role),
                    "wall_index": self._layout.wall_index.get(role),
                    "connected": role in self._connections,
                    "state": state.value,
                    "view": VIEW_BLACKOUT if self._blackout else _VIEW_BY_STATE[state],
                    "chat_open": session is not None,
                    "chat_started_at": session.started_at if session is not None else None,
                    "slide_title": slide.title if slide is not None else None,
                }
            )
        return AdminSnapshotMsg(
            blackout=self._blackout,
            started_at=self._started_at,
            wall_count=self._layout.wall_count,
            screens=screens,
            slides=self._slide_band.buttons(self._layout.roles),
            stats={
                "chats_today": self._chats_today,
                "avg_chat_seconds": self._avg_chat_seconds,
                "ai_errors_today": self._ai_errors_today,
            },
        )

    async def _publish_admin(self) -> None:
        self._admin_dirty = False
        if self._send_admin is not None:
            await self._send_admin(self.admin_snapshot())
