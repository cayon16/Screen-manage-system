import pytest

from app.commands import (
    AdminCommand,
    AdminConnectedCommand,
    ChatMessageCommand,
    ClientConnectedCommand,
    ClientDisconnectedCommand,
    HostActivityCommand,
    LayoutCommand,
    SelectSlideCommand,
    SlicesReadyCommand,
    TouchCommand,
)
from app.state.cluster_controller import ClusterController
from app.state.layout import ClusterLayout, LayoutError
from app.state.screen_fsm import ScreenState
from app.superdoc.manager import AiManager

from tests.conftest import FakeProvider
from tests.test_chat_flow import _drain


def _touch(screen_id: int, target: str) -> TouchCommand:
    return TouchCommand(screen_id=screen_id, target=target)


def _layout(*roles_left_to_right: int) -> LayoutCommand:
    return LayoutCommand(
        layout=ClusterLayout.from_displays((role, i) for i, role in enumerate(roles_left_to_right))
    )


class AdminRecorder:
    def __init__(self):
        self.snapshots = []

    async def __call__(self, snapshot):
        self.snapshots.append(snapshot)

    @property
    def last(self):
        return self.snapshots[-1]

    def screen(self, role: int) -> dict:
        return next(s for s in self.last.screens if s["role"] == role)


class FakeSlicer:
    def __init__(self):
        self.ready_counts: set[int] = set()
        self.ensured: list[int] = []

    def ready(self, wall_count: int) -> bool:
        return wall_count in self.ready_counts

    def ensure(self, wall_count: int) -> None:
        self.ensured.append(wall_count)


@pytest.fixture
def admin() -> AdminRecorder:
    return AdminRecorder()


@pytest.fixture
def slicer() -> FakeSlicer:
    return FakeSlicer()


@pytest.fixture
def controller(sender, provider, store, admin, slicer) -> ClusterController:
    # Ghi de fixture chung: controller nay co them kenh quan ly va bo cat video gia.
    return ClusterController(
        send=sender, provider=provider, store=store, send_admin=admin, slicer=slicer
    )


# ---------- ClusterLayout ----------


def test_default_layout_is_five_screens_in_role_order():
    layout = ClusterLayout.default()
    assert layout.roles == (1, 2, 3, 4, 5)
    assert layout.wall_index == {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}


@pytest.mark.parametrize(
    "displays",
    [
        [],
        [(6, 0)],
        [(1, 0), (1, 1)],
        [(1, 0), (2, 2)],
        [(1, 1)],
    ],
    ids=["rong", "vai-tro-la", "trung-vai-tro", "vi-tri-nhay-coc", "vi-tri-khong-tu-0"],
)
def test_invalid_layouts_are_rejected(displays):
    with pytest.raises(LayoutError):
        ClusterLayout.from_displays(displays)


def test_layout_lists_displays_left_to_right():
    layout = ClusterLayout.from_displays([(1, 1), (2, 0), (3, 2)])
    assert layout.roles == (1, 2, 3)
    assert [d["role"] for d in layout.as_dict()["displays"]] == [2, 1, 3]


# ---------- bo cuc it man ----------


async def test_three_plain_screens_work_as_roles_1_2_3(controller, sender):
    await controller._handle(_layout(1, 2, 3))

    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))

    assert controller.state_of(1) == ScreenState.SLIDE_MEMBER
    assert controller.state_of(3) == ScreenState.SLIDE_MEMBER
    # Vai tro 4, 5 khong ton tai -> khong duoc dong den, khong nhan message nao.
    assert controller.state_of(4) == ScreenState.STANDBY
    assert controller.state_of(5) == ScreenState.STANDBY
    assert sender.to(4) == [] and sender.to(5) == []
    # Bang dieu khien chi con nut cua man 1 va man 3.
    panel = sender.to(2, "state_update")[-1]
    assert {b["screen_id"] for b in panel.data["buttons"]} == {1, 3}
    assert set(panel.data["current"]) == {"1", "3"}


async def test_touch_from_a_role_that_is_not_in_the_layout_is_ignored(controller, sender):
    await controller._handle(_layout(1, 2, 3))
    before = len(sender.messages)

    await controller._handle(_touch(4, "chat_button"))

    assert controller.state_of(4) == ScreenState.STANDBY
    assert controller.session_of(4) is None
    assert len(sender.messages) == before


async def test_single_chat_screen_can_chat_without_a_control_screen(controller):
    await controller._handle(_layout(4))

    await controller._handle(_touch(4, "chat_button"))

    assert controller.state_of(4) == ScreenState.CHAT
    assert controller.state_of(2) == ScreenState.STANDBY


async def test_slide_only_wall_wakes_on_host_activity_and_sleeps_on_tier2(controller):
    await controller._handle(_layout(1, 3))

    await controller._handle(HostActivityCommand())
    assert controller.state_of(1) == ScreenState.SLIDE_MEMBER
    assert controller.state_of(3) == ScreenState.SLIDE_MEMBER
    assert controller._tier2_timer.is_active is True

    await controller._handle_tier2_fired()
    assert controller.state_of(1) == ScreenState.STANDBY
    assert controller.state_of(3) == ScreenState.STANDBY


async def test_standby_position_follows_the_wall_not_the_role_number(controller, sender):
    # Man cam ung (vai tro 2) dung ben trai cung -> no la lat video dau tien.
    await controller._handle(_layout(2, 1, 3))

    data2 = sender.to(2, "state_update")[-1].data
    data1 = sender.to(1, "state_update")[-1].data
    assert (data2["crop_index"], data2["crop_count"]) == (0, 3)
    assert (data1["crop_index"], data1["crop_count"]) == (1, 3)
    assert data2["video_src"] == "/standby-video"
    assert data2["screen_index"] == 0 and data2["screen_count"] == 3


async def test_removing_a_screen_closes_its_chat(controller, sender):
    await controller._handle(_touch(4, "chat_button"))
    session_id = controller.session_of(4).session_id

    await controller._handle(_layout(1, 2, 3, 5))

    assert controller.session_of(4) is None
    assert controller.state_of(4) == ScreenState.STANDBY
    closed = sender.to(4, "session_closed")[-1]
    assert (closed.session_id, closed.reason) == (session_id, "screen_removed")
    # Khong con phien chat nao -> dem nguoc ngu cua ca cum phai chay lai.
    assert controller._tier2_timer.is_active is True


async def test_screen_plugged_in_while_awake_joins_in_its_awake_state(controller):
    await controller._handle(_layout(1, 2))
    await controller._handle(_touch(2, "generic_wake"))

    await controller._handle(_layout(1, 2, 3, 4))

    assert controller.state_of(3) == ScreenState.SLIDE_MEMBER
    assert controller.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON
    assert controller.state_of(2) == ScreenState.MENU


async def test_screen_plugged_in_while_asleep_stays_asleep(controller):
    await controller._handle(_layout(1, 2))

    await controller._handle(_layout(1, 2, 3))

    assert controller.state_of(3) == ScreenState.STANDBY


# ---------- lat video cat san ----------


async def test_layout_change_asks_for_matching_slices(controller, slicer):
    await controller._handle(_layout(1, 2, 3))
    assert slicer.ensured == [3]


async def test_ready_slices_are_used_instead_of_cropping_the_full_video(controller, sender, slicer):
    slicer.ready_counts.add(5)

    await controller._handle(ClientConnectedCommand(screen_id=3, conn_id="a"))

    data = sender.to(3, "state_update")[-1].data
    assert data["video_src"] == "/standby-video/5/2"
    assert (data["crop_index"], data["crop_count"]) == (0, 1)


async def test_slices_ready_refreshes_only_standby_screens(controller, sender, slicer):
    await controller._handle(_touch(4, "chat_button"))
    before4 = len(sender.to(4, "state_update"))
    slicer.ready_counts.add(5)

    await controller._handle(SlicesReadyCommand(wall_count=5))

    # Ca cum dang thuc -> khong man nao o STANDBY -> khong gui gi.
    assert len(sender.to(4, "state_update")) == before4

    await controller._handle_tier2_fired()
    await controller._handle(SlicesReadyCommand(wall_count=5))
    assert sender.to(1, "state_update")[-1].data["video_src"] == "/standby-video/5/0"


async def test_slices_for_an_old_layout_are_ignored(controller, sender):
    await controller._handle(_layout(1, 2, 3))
    before = len(sender.messages)

    await controller._handle(SlicesReadyCommand(wall_count=5))

    assert len(sender.messages) == before


# ---------- anh chup cho man quan ly ----------


async def test_admin_gets_a_snapshot_when_it_connects(controller, admin):
    await controller._handle(AdminConnectedCommand())

    snap = admin.last
    assert snap.type == "admin_snapshot"
    assert snap.wall_count == 5
    assert [s["role"] for s in snap.screens] == [1, 2, 3, 4, 5]
    assert all(s["active"] and not s["connected"] for s in snap.screens)
    assert len(snap.slides) == 6
    assert snap.stats == {"chats_today": 0, "avg_chat_seconds": None, "ai_errors_today": 0}


async def test_one_snapshot_per_command_even_if_many_screens_change(controller, admin):
    await controller._handle(_touch(2, "generic_wake"))
    assert len(admin.snapshots) == 1
    assert admin.screen(1)["view"] == "slide"
    assert admin.screen(2)["view"] == "menu"


async def test_connection_status_ignores_a_late_disconnect_of_an_old_connection(controller, admin):
    await controller._handle(ClientConnectedCommand(screen_id=2, conn_id="cu"))
    await controller._handle(ClientConnectedCommand(screen_id=2, conn_id="moi"))

    await controller._handle(ClientDisconnectedCommand(screen_id=2, conn_id="cu"))
    assert admin.screen(2)["connected"] is True

    await controller._handle(ClientDisconnectedCommand(screen_id=2, conn_id="moi"))
    assert admin.screen(2)["connected"] is False


async def test_snapshot_shows_open_chat_and_inactive_screens(controller, admin):
    await controller._handle(_layout(1, 2, 3, 4))
    await controller._handle(_touch(4, "chat_button"))

    assert admin.screen(4)["chat_open"] is True
    assert admin.screen(4)["chat_started_at"] is not None
    assert admin.screen(5)["active"] is False
    assert admin.screen(5)["wall_index"] is None
    assert admin.last.wall_count == 4
    assert {b["screen_id"] for b in admin.last.slides} == {1, 3}


async def test_stats_count_todays_chats_and_ai_errors(controller, admin, store):
    controller._ai = AiManager.fixed(FakeProvider(fail=True))
    await controller._handle(_touch(4, "chat_button"))
    session_id = controller.session_of(4).session_id
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Chào"))
    await _drain(controller)
    assert admin.last.stats["ai_errors_today"] == 1

    await controller._handle(_touch(4, "exit_chat"))

    stats = admin.last.stats
    assert stats["chats_today"] == 1
    assert stats["avg_chat_seconds"] is not None


# ---------- lenh quan ly ----------


async def test_admin_can_pick_a_slide_without_touching_screen_2(controller, sender, admin):
    await controller._handle(_touch(2, "generic_wake"))  # man 2 dang o MENU, khong phai bang dieu khien

    await controller._handle(AdminCommand(action="select_slide", slide_id="noi_quy"))

    assert sender.to(3, "state_update")[-1].data["slide"]["id"] == "noi_quy"
    assert admin.screen(3)["slide_title"] == next(
        b["title"] for b in admin.last.slides if b["slide_id"] == "noi_quy"
    )


async def test_admin_slide_for_a_missing_screen_is_ignored(controller, sender):
    await controller._handle(_layout(1, 2))
    before = len(sender.messages)

    await controller._handle(AdminCommand(action="select_slide", slide_id="noi_quy"))  # thuoc man 3

    assert len(sender.messages) == before


async def test_force_standby_ends_chats_and_puts_everything_to_sleep(controller, sender):
    await controller._handle(_touch(4, "chat_button"))

    await controller._handle(AdminCommand(action="force_standby"))

    for role in (1, 2, 3, 4, 5):
        assert controller.state_of(role) == ScreenState.STANDBY
    assert sender.to(4, "session_closed")[-1].reason == "cluster_reset"
    assert controller._tier2_timer.is_active is False


async def test_blackout_turns_every_screen_black_and_ends_chats(controller, sender, admin):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(4, "chat_button"))

    await controller._handle(AdminCommand(action="blackout_on"))

    assert sender.to(4, "session_closed")[-1].reason == "blackout"
    for role in (1, 2, 3, 4, 5):
        assert controller.state_of(role) == ScreenState.STANDBY
        assert sender.to(role, "state_update")[-1].view == "blackout"
    assert controller._tier2_timer.is_active is False
    assert admin.last.blackout is True
    assert admin.screen(1)["view"] == "blackout"


async def test_blackout_ignores_touch_host_activity_and_slide_picks(controller, sender):
    await controller._handle(AdminCommand(action="blackout_on"))
    before = len(sender.messages)

    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(HostActivityCommand())
    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="noi_quy"))
    await controller._handle(AdminCommand(action="select_slide", slide_id="noi_quy"))
    await controller._handle(AdminCommand(action="force_standby"))

    assert len(sender.messages) == before
    assert controller.session_of(4) is None
    assert controller._tier2_timer.is_active is False


async def test_screen_that_reconnects_during_blackout_stays_black(controller, sender):
    await controller._handle(AdminCommand(action="blackout_on"))

    await controller._handle(ClientConnectedCommand(screen_id=3, conn_id="x"))
    await controller._handle(_layout(1, 2, 3))

    assert sender.to(3, "state_update")[-1].view == "blackout"


async def test_turning_blackout_off_returns_to_standby_and_touch_works_again(controller, sender):
    await controller._handle(AdminCommand(action="blackout_on"))

    await controller._handle(AdminCommand(action="blackout_off"))

    for role in (1, 2, 3, 4, 5):
        assert sender.to(role, "state_update")[-1].view == "standby"
    await controller._handle(_touch(2, "generic_wake"))
    assert controller.state_of(2) == ScreenState.MENU


async def test_reset_restores_default_slides_and_leaves_blackout(controller, sender, admin):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(AdminCommand(action="select_slide", slide_id="noi_quy"))
    await controller._handle(AdminCommand(action="blackout_on"))

    await controller._handle(AdminCommand(action="reset"))

    assert controller.blackout is False
    for role in (1, 2, 3, 4, 5):
        assert controller.state_of(role) == ScreenState.STANDBY
        assert sender.to(role, "state_update")[-1].view == "standby"
    slides = admin.last.slides
    first_of_screen_3 = next(b for b in slides if b["screen_id"] == 3)
    assert first_of_screen_3["current"] is True


async def test_reset_closes_chats_with_its_own_reason(controller, sender):
    await controller._handle(_touch(4, "chat_button"))

    await controller._handle(AdminCommand(action="reset"))

    assert sender.to(4, "session_closed")[-1].reason == "system_reset"
    assert controller.session_of(4) is None
