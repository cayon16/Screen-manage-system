import asyncio

from app.commands import HostActivityCommand, SelectSlideCommand, Tier2FiredCommand, TouchCommand
from app.state import cluster_controller as cc_module
from app.state.cluster_controller import ClusterController
from app.state.screen_fsm import ScreenState


def _touch(screen_id: int, target: str) -> TouchCommand:
    return TouchCommand(screen_id=screen_id, target=target)


# ---------- Luong A: danh thuc ----------


async def test_waking_up_returns_every_screen_to_its_own_normal_function(controller):
    # descryption.txt muc 2: thoat Standby thi "ca 5 man deu quay ve chuc nang von co cua no" —
    # man 1/3/5 len slide ngay, khong cho toi luc co nguoi bam "Thong tin benh vien".
    await controller._handle(_touch(2, "generic_wake"))

    assert controller.state_of(2) == ScreenState.MENU
    assert controller.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON
    for screen_id in (1, 3, 5):
        assert controller.state_of(screen_id) == ScreenState.SLIDE_MEMBER


async def test_waking_by_touching_the_chat_screen_also_starts_the_slides(controller):
    await controller._handle(_touch(4, "chat_button"))

    assert controller.state_of(4) == ScreenState.CHAT
    assert controller.state_of(2) == ScreenState.MENU
    for screen_id in (1, 3, 5):
        assert controller.state_of(screen_id) == ScreenState.SLIDE_MEMBER


async def test_touching_again_while_already_awake_does_not_disturb_the_slides(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="quy_trinh_kham"))
    before = len(sender.to(3, "state_update"))

    await controller._handle(_touch(2, "generic_wake"))

    # Da thuc san roi thi cham them khong duoc phep reset slide dang chieu ve mac dinh.
    assert len(sender.to(3, "state_update")) == before
    assert sender.to(3, "state_update")[-1].data["slide"]["id"] == "quy_trinh_kham"


async def test_touch_chat_screen_direct_goes_to_chat_and_wakes_control(controller, sender):
    await controller._handle(_touch(4, "chat_button"))

    assert controller.state_of(4) == ScreenState.CHAT
    assert controller.state_of(2) == ScreenState.MENU
    assert sender.to(4, "state_update")[-1].data.get("session_id") is not None


async def test_host_activity_wakes_touch_screens_when_everything_is_asleep(controller):
    # Dac ta: thao tac chuot/phim tren MAY CHU cung phai keo he thong ra khoi Standby.
    await controller._handle(HostActivityCommand())

    assert controller.state_of(2) == ScreenState.MENU
    assert controller.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON
    assert controller._tier2_timer.is_active is True


async def test_host_activity_while_chatting_does_not_disturb_the_chat(controller):
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(HostActivityCommand())

    assert controller.state_of(4) == ScreenState.CHAT
    assert controller.session_of(4) is not None


# ---------- Luong B: trinh chieu ----------


async def test_menu_select_info_puts_only_passive_screens_on_slides(controller):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))

    for screen_id in (1, 3, 5):
        assert controller.state_of(screen_id) == ScreenState.SLIDE_MEMBER
    assert controller.state_of(2) == ScreenState.SLIDE_CONTROL
    assert controller.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON


async def test_slide_control_panel_offers_exactly_six_buttons(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))

    panel = sender.to(2, "state_update")[-1]
    assert len(panel.data["buttons"]) == 6
    assert {b["screen_id"] for b in panel.data["buttons"]} == {1, 3, 5}


async def test_select_slide_only_changes_the_screen_that_owns_it(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))
    before_screen1 = len(sender.to(1, "state_update"))

    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="noi_quy"))

    assert sender.to(3, "state_update")[-1].data["slide"]["id"] == "noi_quy"
    # Man 1 va man 5 khong duoc dong den — moi man 1 noi dung doc lap.
    assert len(sender.to(1, "state_update")) == before_screen1


async def test_select_slide_is_ignored_when_control_screen_is_not_on_the_panel(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))  # dang o MENU, chua bat trinh chieu
    before = len(sender.messages)

    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="noi_quy"))

    assert len(sender.messages) == before


async def test_unknown_slide_id_is_ignored(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))
    before = len(sender.messages)

    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="khong_ton_tai"))

    assert len(sender.messages) == before


# ---------- Luong C + D: chat doc lap, hanh vi cheo ----------


async def test_chat_screen_touch_during_band_does_not_disturb_slide_screens(controller):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))

    await controller._handle(_touch(4, "chat_button"))

    assert controller.state_of(4) == ScreenState.CHAT
    for screen_id in (1, 3, 5):
        assert controller.state_of(screen_id) == ScreenState.SLIDE_MEMBER
    assert controller.state_of(2) == ScreenState.SLIDE_CONTROL


async def test_two_screens_chat_at_the_same_time_with_separate_sessions(controller):
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(_touch(2, "menu_option_chat"))

    session2 = controller.session_of(2)
    session4 = controller.session_of(4)
    assert session2 is not None and session4 is not None
    assert session2.session_id != session4.session_id


async def test_exiting_chat_on_one_screen_leaves_the_other_untouched(controller):
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(_touch(2, "menu_option_chat"))
    session4_id = controller.session_of(4).session_id

    await controller._handle(_touch(2, "exit_chat"))

    assert controller.session_of(2) is None
    assert controller.state_of(2) == ScreenState.MENU
    assert controller.state_of(4) == ScreenState.CHAT
    assert controller.session_of(4).session_id == session4_id


async def test_control_switch_from_chat_to_info_needs_confirmation(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_chat"))
    await controller._handle(_touch(2, "menu_option_info"))

    assert controller.state_of(2) == ScreenState.CHAT_CONFIRM_SWITCH
    assert controller.session_of(2) is not None  # chua dong session khi chua xac nhan
    # Giao dien hien hop thoai xac nhan theo chinh state nay, backend khong gui them message.
    assert sender.to(2, "state_update")[-1].state == "CHAT_CONFIRM_SWITCH"


async def test_confirming_the_switch_closes_the_session_and_starts_the_band(controller):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_chat"))
    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(_touch(2, "confirm_yes"))

    assert controller.session_of(2) is None
    assert controller.state_of(2) == ScreenState.SLIDE_CONTROL
    for screen_id in (1, 3, 5):
        assert controller.state_of(screen_id) == ScreenState.SLIDE_MEMBER


async def test_cancelling_the_switch_keeps_the_same_session(controller):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_chat"))
    original_id = controller.session_of(2).session_id
    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(_touch(2, "confirm_no"))

    assert controller.state_of(2) == ScreenState.CHAT
    assert controller.session_of(2).session_id == original_id


async def test_control_exits_chat_to_the_menu_without_touching_the_slide_screens(controller, sender):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="quy_trinh_kham"))
    await controller._handle(_touch(2, "menu_option_chat"))
    updates_before = {sid: len(sender.to(sid, "state_update")) for sid in (1, 3, 5)}

    await controller._handle(_touch(2, "exit_chat"))

    assert controller.state_of(2) == ScreenState.MENU
    # Man 1/3/5 "van hoat dong nhu truoc do, khong thay doi gi" — khong nhan them message nao.
    for sid in (1, 3, 5):
        assert len(sender.to(sid, "state_update")) == updates_before[sid]
    assert sender.to(3, "state_update")[-1].data["slide"]["id"] == "quy_trinh_kham"


async def test_reconnecting_screen_gets_back_exactly_what_it_was_showing(controller, sender):
    # Tren may chay 24/7, 1 cua so trinh duyet co the bi dong/mo lai. Khi ket noi lai no phai
    # nhan dung slide dang chieu, khong phai quay ve mac dinh.
    from app.commands import ClientConnectedCommand

    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(SelectSlideCommand(screen_id=2, slide_id="quy_trinh_kham"))

    await controller._handle(ClientConnectedCommand(screen_id=3))

    snapshot = sender.to(3, "state_update")[-1]
    assert snapshot.state == "SLIDE_MEMBER"
    assert snapshot.data["slide"]["id"] == "quy_trinh_kham"


async def test_chat_screen_returns_to_prompt_button_after_exit(controller):
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(_touch(4, "exit_chat"))

    assert controller.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON
    assert controller.session_of(4) is None


# ---------- Tier-2 ----------


async def test_tier2_fired_resets_everything_to_standby(controller):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_info"))

    await controller._handle(Tier2FiredCommand())

    for screen_id in (1, 2, 3, 4, 5):
        assert controller.state_of(screen_id) == ScreenState.STANDBY


async def test_tier2_timer_does_not_restart_itself_immediately_after_firing(
    monkeypatch, sender, provider, store
):
    # Bug da bat trong qua trinh thiet ke: goi _refresh_tier2_timer() vo dieu kien sau
    # CLUSTER_RESET se khien timer tu khoi dong lai vinh vien du khong con hoat dong gi.
    # Can timer THAT SU no (khong phai dispatch Command thu cong) de tai hien dung bug nay.
    monkeypatch.setattr(cc_module, "TIER2_CLUSTER_IDLE_SEC", 0.05)
    ctrl = ClusterController(send=sender, provider=provider, store=store)
    task = asyncio.create_task(ctrl.run())
    try:
        await ctrl.submit(_touch(2, "generic_wake"))
        await ctrl.wait_idle()
        assert ctrl._tier2_timer.is_active is True

        await asyncio.sleep(0.2)  # cho timer 0.05s no + queue xu ly xong Tier2FiredCommand
        await ctrl.wait_idle()

        assert ctrl.state_of(2) == ScreenState.STANDBY
        assert ctrl._tier2_timer.is_active is False
    finally:
        ctrl.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_tier2_timer_gating_by_open_chat_session(controller):
    await controller._handle(_touch(4, "chat_button"))  # mo phien chat -> gate dong
    assert controller._tier2_timer.is_active is False

    await controller._handle(_touch(4, "exit_chat"))  # dong phien -> gate mo lai
    assert controller._tier2_timer.is_active is True


async def test_tier2_stays_disabled_while_the_second_screen_is_still_chatting(controller):
    await controller._handle(_touch(4, "chat_button"))
    await controller._handle(_touch(2, "menu_option_chat"))

    await controller._handle(_touch(2, "exit_chat"))

    # Man 4 van dang chat -> chua duoc phep hen gio ngu cho ca cum.
    assert controller._tier2_timer.is_active is False


# ---------- state_update payload ----------


async def test_standby_payload_carries_shared_clock_and_screen_position(controller, sender):
    from app.commands import ClientConnectedCommand

    await controller._handle(ClientConnectedCommand(screen_id=3))

    data = sender.to(3, "state_update")[-1].data
    assert data["screen_index"] == 2  # man 3 la man thu 3 tu trai (index 0-based)
    assert data["screen_count"] == 5
    assert data["video_src"] == "/standby-video"
    assert data["server_now"] >= data["t0"]


async def test_every_screen_gets_a_different_slice_index_of_the_same_video(controller, sender):
    # 5 man phai cung phat 1 video nhung moi man mot lat cat khac nhau; neu 2 man nhan cung
    # screen_index thi hinh se bi lap va tuong man hinh khong con lien mach.
    from app.commands import ClientConnectedCommand

    for sid in (1, 2, 3, 4, 5):
        await controller._handle(ClientConnectedCommand(screen_id=sid))

    payloads = {sid: sender.to(sid, "state_update")[-1].data for sid in (1, 2, 3, 4, 5)}
    assert [payloads[sid]["screen_index"] for sid in (1, 2, 3, 4, 5)] == [0, 1, 2, 3, 4]
    assert {payloads[sid]["video_src"] for sid in (1, 2, 3, 4, 5)} == {"/standby-video"}
    # Cung 1 moc thoi gian goc cho ca 5 man — day la thu giu chung khong troi khoi nhau.
    assert len({payloads[sid]["t0"] for sid in (1, 2, 3, 4, 5)}) == 1
