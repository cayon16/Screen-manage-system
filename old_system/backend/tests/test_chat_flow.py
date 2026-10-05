import asyncio

from app.commands import ChatMessageCommand, Tier1AckCommand, TouchCommand
from app.state.screen_fsm import ScreenState

from tests.conftest import FakeProvider


def _touch(screen_id: int, target: str) -> TouchCommand:
    return TouchCommand(screen_id=screen_id, target=target)


async def _open_chat(controller, screen_id: int = 4) -> str:
    await controller._handle(_touch(screen_id, "chat_button"))
    return controller.session_of(screen_id).session_id


async def _drain(controller) -> None:
    """Task goi AI chay NGOAI hang doi command (co y do: 1 phien cham khong duoc lam dong ca he
    thong). Cac test nay goi _handle() truc tiep chu khong chay run(), nen phai tu nhuong dieu
    khien cho task do va tu tieu thu command ma no day vao."""
    for _ in range(20):
        await asyncio.sleep(0)
        while not controller._queue.empty():
            command = controller._queue.get_nowait()
            await controller._handle(command)
            controller._queue.task_done()


# ---------- di het 1 luot hoi - dap ----------


async def test_user_question_reaches_ai_and_answer_comes_back(controller, sender, provider):
    session_id = await _open_chat(controller)

    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Mấy giờ khám?"))
    assert controller.session_of(4).waiting_for_ai is True

    await _drain(controller)

    acks = sender.to(4, "chat_message_ack")
    assert len(acks) == 1
    assert acks[-1].role == "assistant"
    assert acks[-1].text == provider.answer
    assert controller.session_of(4).waiting_for_ai is False


async def test_history_grows_and_is_passed_to_the_provider(controller, provider):
    session_id = await _open_chat(controller)

    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Câu 1"))
    await _drain(controller)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Câu 2"))
    await _drain(controller)

    # Luot goi thu 2 phai nhin thay ca 3 luot truoc do (hoi 1, dap 1, hoi 2).
    assert [t.text for t in provider.calls[-1]] == ["Câu 1", provider.answer, "Câu 2"]


async def test_empty_message_is_ignored(controller, sender):
    session_id = await _open_chat(controller)
    before = len(sender.messages)

    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="   "))

    assert len(sender.messages) == before
    assert controller.session_of(4).waiting_for_ai is False


async def test_message_with_stale_session_id_is_rejected(controller, sender):
    await _open_chat(controller)
    before = len(sender.messages)

    await controller._handle(
        ChatMessageCommand(screen_id=4, session_id="phien-cu-da-dong", text="Xin chào")
    )

    assert len(sender.messages) == before


# ---------- luu database ----------


async def test_whole_conversation_is_persisted(controller, store, provider):
    session_id = await _open_chat(controller)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Giờ khám?"))
    await _drain(controller)

    assert store.fetch_messages(session_id) == [
        ("user", "Giờ khám?"),
        ("assistant", provider.answer),
    ]

    row = store.fetch_session(session_id)
    assert row[1] == 4  # screen_id
    assert row[3] is None  # chua dong


async def test_closing_the_chat_records_the_reason_but_keeps_the_transcript(controller, store):
    session_id = await _open_chat(controller)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Xin chào"))
    await _drain(controller)

    await controller._handle(_touch(4, "exit_chat"))

    row = store.fetch_session(session_id)
    assert row[3] is not None  # ended_at
    assert row[4] == "user_exit"
    # Lich su trong bo nho bi xoa, nhung ban ghi trong database phai con nguyen ven.
    assert len(store.fetch_messages(session_id)) == 2


async def test_closing_the_chat_tells_the_ai_the_session_ended(controller, provider):
    # descryption.txt muc 3: "API cần ... thông báo cho AI kết thúc đoạn chat nếu cần".
    session_id = await _open_chat(controller)
    await controller._handle(_touch(4, "exit_chat"))

    assert provider.ended_sessions == [session_id]


async def test_mode_switch_is_recorded_as_its_own_reason(controller, store):
    await controller._handle(_touch(2, "generic_wake"))
    await controller._handle(_touch(2, "menu_option_chat"))
    session_id = controller.session_of(2).session_id

    await controller._handle(_touch(2, "menu_option_info"))
    await controller._handle(_touch(2, "confirm_yes"))

    assert store.fetch_session(session_id)[4] == "mode_switch"


# ---------- Tier-1 ----------


async def test_tier1_warning_then_cleanup_ends_the_chat(monkeypatch, sender, provider, store):
    from app.state import chat_session as cs_module
    from app.state.cluster_controller import ClusterController

    monkeypatch.setattr(cs_module, "TIER1_WARNING_SEC", 0.05)
    monkeypatch.setattr(cs_module, "TIER1_CLEANUP_SEC", 0.20)

    ctrl = ClusterController(send=sender, provider=provider, store=store)
    task = asyncio.create_task(ctrl.run())
    try:
        await ctrl.submit(_touch(4, "chat_button"))
        await ctrl.wait_idle()
        assert ctrl.state_of(4) == ScreenState.CHAT

        await asyncio.sleep(0.10)  # qua moc canh bao, chua toi moc don dep
        await ctrl.wait_idle()
        warnings = sender.to(4, "confirm_prompt")
        assert warnings and warnings[-1].kind == "tier1_warning"
        assert ctrl.state_of(4) == ScreenState.CHAT  # canh bao chua ket thuc chat

        await asyncio.sleep(0.25)  # qua han don dep
        await ctrl.wait_idle()

        assert ctrl.session_of(4) is None
        assert ctrl.state_of(4) == ScreenState.PROMPT_CHAT_BUTTON
        assert sender.to(4, "session_closed")[-1].reason == "tier1_timeout"
    finally:
        ctrl.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_tier1_ack_keeps_the_chat_alive(monkeypatch, sender, provider, store):
    from app.state import chat_session as cs_module
    from app.state.cluster_controller import ClusterController

    monkeypatch.setattr(cs_module, "TIER1_WARNING_SEC", 0.05)
    monkeypatch.setattr(cs_module, "TIER1_CLEANUP_SEC", 10.0)

    ctrl = ClusterController(send=sender, provider=provider, store=store)
    task = asyncio.create_task(ctrl.run())
    try:
        await ctrl.submit(_touch(4, "chat_button"))
        await ctrl.wait_idle()
        session = ctrl.session_of(4)

        await asyncio.sleep(0.10)  # canh bao da hien, dong ho don dep dang chay
        await ctrl.wait_idle()
        assert session._cleanup_timer.is_active is True

        await ctrl.submit(Tier1AckCommand(screen_id=4, session_id=session.session_id))
        await ctrl.wait_idle()

        # Bam "Toi van o day" phai huy han don dep va bat dau dem lai tu dau.
        assert session._cleanup_timer.is_active is False
        assert session._warning_timer.is_active is True
        assert ctrl.session_of(4) is session
        assert ctrl.state_of(4) == ScreenState.CHAT
    finally:
        ctrl.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_waiting_for_ai_does_not_count_as_the_user_walking_away(controller):
    session_id = await _open_chat(controller)
    session = controller.session_of(4)

    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Câu hỏi"))

    # Trong luc AI dang nghi, dong ho Tier-1 phai dung han — khong dem nham thanh im lang.
    assert session.waiting_for_ai is True
    assert session._warning_timer.is_active is False
    assert session._cleanup_timer.is_active is False

    await _drain(controller)
    assert session._warning_timer.is_active is True


# ---------- loi AI ----------


async def test_ai_failure_shows_a_local_error_and_arms_the_cleanup_timer(sender, store):
    from app.state.cluster_controller import ClusterController

    ctrl = ClusterController(send=sender, provider=FakeProvider(fail=True), store=store)
    await ctrl._handle(_touch(4, "chat_button"))
    session_id = ctrl.session_of(4).session_id

    await ctrl._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Xin chào"))
    await _drain(ctrl)

    errors = sender.to(4, "error")
    assert errors and errors[-1].code == "ai_unavailable"
    session = ctrl.session_of(4)
    assert session.in_error is True
    assert session._error_timer.is_active is True
    ctrl.stop()


async def test_error_on_one_screen_does_not_touch_the_other_screen(sender, store):
    from app.state.cluster_controller import ClusterController

    ctrl = ClusterController(send=sender, provider=FakeProvider(fail=True), store=store)
    await ctrl._handle(_touch(4, "chat_button"))  # danh thuc ca doi -> man 2 hien MENU
    await ctrl._handle(_touch(2, "menu_option_chat"))
    session4 = ctrl.session_of(4).session_id

    await ctrl._handle(ChatMessageCommand(screen_id=4, session_id=session4, text="Xin chào"))
    await _drain(ctrl)

    assert ctrl.state_of(2) == ScreenState.CHAT
    assert ctrl.session_of(2).in_error is False
    assert sender.to(2, "error") == []
    ctrl.stop()


async def test_touching_the_screen_during_an_error_keeps_the_session_alive(sender, store):
    # Dong ho don dep sau loi sinh ra de don man hinh treo thong bao loi ma KHONG CO AI dung do.
    # Neu nguoi dung van dang cham man, no khong duoc phep dong phien chat cua ho giua chung.
    from app.state.cluster_controller import ClusterController

    ctrl = ClusterController(send=sender, provider=FakeProvider(fail=True), store=store)
    await ctrl._handle(_touch(4, "chat_button"))
    session_id = ctrl.session_of(4).session_id

    await ctrl._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Xin chào"))
    await _drain(ctrl)
    session = ctrl.session_of(4)
    assert session._error_timer.is_active is True

    await ctrl._handle(_touch(4, "generic_wake"))

    assert session._error_timer.is_active is False
    assert session._warning_timer.is_active is True  # Tier-1 tiep quan viec don dep
    assert ctrl.session_of(4) is session
    ctrl.stop()


async def test_message_sent_while_the_ai_is_still_answering_is_refused(controller, provider):
    # 2 luot "user" lien tiep trong lich su se lam Gemini that tu choi payload.
    session_id = await _open_chat(controller)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Câu 1"))
    assert controller.session_of(4).waiting_for_ai is True

    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Câu 2"))
    await _drain(controller)

    roles = [t.role for t in controller.session_of(4).history]
    assert roles == ["user", "assistant"]
    assert [t.text for t in controller.session_of(4).history][0] == "Câu 1"


async def test_asking_again_after_an_error_clears_the_error(sender, store):
    from app.state.cluster_controller import ClusterController

    provider = FakeProvider(fail=True)
    ctrl = ClusterController(send=sender, provider=provider, store=store)
    await ctrl._handle(_touch(4, "chat_button"))
    session_id = ctrl.session_of(4).session_id

    await ctrl._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Lần 1"))
    await _drain(ctrl)
    assert ctrl.session_of(4).in_error is True

    provider.fail = False
    await ctrl._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Lần 2"))
    await _drain(ctrl)

    session = ctrl.session_of(4)
    assert session.in_error is False
    assert session._error_timer.is_active is False
    ctrl.stop()


async def test_answer_arriving_after_the_session_closed_is_dropped(controller, sender):
    session_id = await _open_chat(controller)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Xin chào"))

    # Nguoi dung bo di va man hinh bi dong phien trong khi AI van dang nghi.
    await controller._handle(_touch(4, "exit_chat"))
    await _drain(controller)

    # Khong duoc phep hien cau tra loi cua nguoi truoc len man hinh da ve trang thai cho.
    assert sender.to(4, "chat_message_ack") == []
