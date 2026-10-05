import pytest

from app.state.screen_fsm import (
    EFFECT_ACTIVATE_BAND,
    EFFECT_CLOSE_CHAT_SESSION,
    EFFECT_OPEN_CHAT_SESSION,
    ScreenEvent,
    ScreenRole,
    ScreenState,
    transition,
)

# ---------- Man 1, 3, 5 (PASSIVE) — 3 man duy nhat trinh chieu slide ----------


def test_passive_band_activate_from_standby():
    result = transition(ScreenRole.PASSIVE, ScreenState.STANDBY, ScreenEvent.BAND_ACTIVATE)
    assert result.new_state == ScreenState.SLIDE_MEMBER
    assert result.effects == ()


def test_passive_cluster_reset_from_slide_member():
    result = transition(ScreenRole.PASSIVE, ScreenState.SLIDE_MEMBER, ScreenEvent.CLUSTER_RESET)
    assert result.new_state == ScreenState.STANDBY
    assert result.effects == ()


def test_passive_ignores_touch_like_events():
    # Man 1/3/5 khong gan input handler — nhung neu 1 event la sai loi vo tinh gui toi,
    # FSM phai an toan bo qua (khong crash, khong tu doi state) thay vi nem loi.
    result = transition(ScreenRole.PASSIVE, ScreenState.STANDBY, ScreenEvent.TOUCH_OWN)
    assert result.handled is False
    assert result.new_state == ScreenState.STANDBY


def test_passive_already_showing_slide_ignores_repeat_band_activate():
    result = transition(ScreenRole.PASSIVE, ScreenState.SLIDE_MEMBER, ScreenEvent.BAND_ACTIVATE)
    assert result.handled is False
    assert result.new_state == ScreenState.SLIDE_MEMBER


# ---------- Man 2 (CONTROL) ----------


@pytest.mark.parametrize("wake_event", [ScreenEvent.TOUCH_OWN, ScreenEvent.WAKE_PAIR])
def test_control_standby_to_menu(wake_event):
    result = transition(ScreenRole.CONTROL, ScreenState.STANDBY, wake_event)
    assert result.new_state == ScreenState.MENU
    assert result.effects == ()


def test_control_menu_select_info_opens_slide_control_panel():
    # Man 2 KHONG tu trinh chieu — no giu bang dieu khien 6 nut de dieu khien man 1/3/5.
    result = transition(ScreenRole.CONTROL, ScreenState.MENU, ScreenEvent.MENU_SELECT_INFO)
    assert result.new_state == ScreenState.SLIDE_CONTROL
    assert EFFECT_ACTIVATE_BAND in result.effects


def test_control_menu_select_chat_opens_session():
    result = transition(ScreenRole.CONTROL, ScreenState.MENU, ScreenEvent.MENU_SELECT_CHAT)
    assert result.new_state == ScreenState.CHAT
    assert EFFECT_OPEN_CHAT_SESSION in result.effects


def test_control_slide_control_back_returns_to_menu():
    result = transition(ScreenRole.CONTROL, ScreenState.SLIDE_CONTROL, ScreenEvent.MENU_BACK)
    assert result.new_state == ScreenState.MENU
    assert result.effects == ()


def test_control_can_open_chat_straight_from_slide_control_panel():
    # "Khong gian doan nen": mo chat tu bang dieu khien khong duoc tat dai slide dang chay.
    result = transition(ScreenRole.CONTROL, ScreenState.SLIDE_CONTROL, ScreenEvent.MENU_SELECT_CHAT)
    assert result.new_state == ScreenState.CHAT
    assert EFFECT_OPEN_CHAT_SESSION in result.effects
    assert EFFECT_ACTIVATE_BAND not in result.effects


def test_control_stray_touch_on_slide_control_panel_changes_nothing():
    # Bang dieu khien co nut "Quay lai menu" ro rang — cham lung tung khong duoc lam mat bang.
    result = transition(ScreenRole.CONTROL, ScreenState.SLIDE_CONTROL, ScreenEvent.TOUCH_OWN)
    assert result.handled is False
    assert result.new_state == ScreenState.SLIDE_CONTROL


def test_control_chat_request_info_asks_confirm():
    result = transition(ScreenRole.CONTROL, ScreenState.CHAT, ScreenEvent.MENU_SELECT_INFO)
    assert result.new_state == ScreenState.CHAT_CONFIRM_SWITCH
    assert result.effects == ()  # chua dong session tai day, chi hoi xac nhan


def test_control_confirm_yes_closes_chat_and_activates_band():
    result = transition(ScreenRole.CONTROL, ScreenState.CHAT_CONFIRM_SWITCH, ScreenEvent.CONFIRM_YES)
    assert result.new_state == ScreenState.SLIDE_CONTROL
    assert EFFECT_CLOSE_CHAT_SESSION in result.effects
    assert EFFECT_ACTIVATE_BAND in result.effects


def test_control_confirm_no_stays_in_chat():
    result = transition(ScreenRole.CONTROL, ScreenState.CHAT_CONFIRM_SWITCH, ScreenEvent.CONFIRM_NO)
    assert result.new_state == ScreenState.CHAT
    assert result.effects == ()


@pytest.mark.parametrize(
    "event",
    [ScreenEvent.CHAT_EXIT, ScreenEvent.TIER1_TIMEOUT, ScreenEvent.ERROR_TIMEOUT],
)
def test_control_every_way_out_of_chat_returns_to_the_two_option_menu(event):
    # descryption.txt muc 3: ket thuc chat (chu dong hay tu dong) deu "tu quay ve trang thai ban
    # dau (man 2 co 2 o la che do trinh chieu va che do chat)" — LUON la MENU, khong phu thuoc
    # dai slide dang chay hay khong. Va KHONG ve thang Standby: Tier-2 moi la tang dua cum di ngu.
    result = transition(ScreenRole.CONTROL, ScreenState.CHAT, event)
    assert result.new_state == ScreenState.MENU
    assert EFFECT_CLOSE_CHAT_SESSION in result.effects


def test_control_timeout_while_confirm_dialog_open_still_cleans_up():
    result = transition(
        ScreenRole.CONTROL, ScreenState.CHAT_CONFIRM_SWITCH, ScreenEvent.TIER1_TIMEOUT
    )
    assert result.new_state == ScreenState.MENU
    assert EFFECT_CLOSE_CHAT_SESSION in result.effects


def test_control_chat_exit_outside_chat_is_ignored():
    result = transition(ScreenRole.CONTROL, ScreenState.MENU, ScreenEvent.CHAT_EXIT)
    assert result.handled is False
    assert result.new_state == ScreenState.MENU


@pytest.mark.parametrize(
    "state",
    [
        ScreenState.STANDBY,
        ScreenState.MENU,
        ScreenState.SLIDE_CONTROL,
        ScreenState.CHAT,
        ScreenState.CHAT_CONFIRM_SWITCH,
    ],
)
def test_control_cluster_reset_from_any_state(state):
    result = transition(ScreenRole.CONTROL, state, ScreenEvent.CLUSTER_RESET)
    assert result.new_state == ScreenState.STANDBY
    if state in (ScreenState.CHAT, ScreenState.CHAT_CONFIRM_SWITCH):
        assert EFFECT_CLOSE_CHAT_SESSION in result.effects
    else:
        assert result.effects == ()


# ---------- Man 4 (CHAT role) ----------


def test_chat_screen_direct_touch_from_standby_goes_straight_to_chat():
    result = transition(ScreenRole.CHAT, ScreenState.STANDBY, ScreenEvent.TOUCH_OWN)
    assert result.new_state == ScreenState.CHAT
    assert EFFECT_OPEN_CHAT_SESSION in result.effects


def test_chat_screen_wake_pair_only_shows_prompt_button():
    result = transition(ScreenRole.CHAT, ScreenState.STANDBY, ScreenEvent.WAKE_PAIR)
    assert result.new_state == ScreenState.PROMPT_CHAT_BUTTON
    assert result.effects == ()  # chua mo session, chi hien nut


def test_chat_screen_prompt_button_touch_opens_chat():
    result = transition(ScreenRole.CHAT, ScreenState.PROMPT_CHAT_BUTTON, ScreenEvent.TOUCH_OWN)
    assert result.new_state == ScreenState.CHAT
    assert EFFECT_OPEN_CHAT_SESSION in result.effects


def test_chat_screen_shows_prompt_button_when_band_activates():
    # Man 4 khong tham gia dai slide — no chi doi sang nut "Cham de chat".
    result = transition(ScreenRole.CHAT, ScreenState.STANDBY, ScreenEvent.BAND_ACTIVATE)
    assert result.new_state == ScreenState.PROMPT_CHAT_BUTTON
    assert result.effects == ()


def test_chat_screen_band_activate_does_not_interrupt_ongoing_chat():
    # Dai slide duoc kich hoat trong khi Man 4 dang chat rieng — khong duoc ngat phien chat.
    result = transition(ScreenRole.CHAT, ScreenState.CHAT, ScreenEvent.BAND_ACTIVATE)
    assert result.handled is False
    assert result.new_state == ScreenState.CHAT


@pytest.mark.parametrize(
    "event",
    [ScreenEvent.CHAT_EXIT, ScreenEvent.TIER1_TIMEOUT, ScreenEvent.ERROR_TIMEOUT],
)
def test_chat_screen_every_way_out_of_chat_returns_to_prompt_button(event):
    # Man 4 "chi co 1 o ghi che do chat" theo dac ta.
    result = transition(ScreenRole.CHAT, ScreenState.CHAT, event)
    assert result.new_state == ScreenState.PROMPT_CHAT_BUTTON
    assert EFFECT_CLOSE_CHAT_SESSION in result.effects


def test_chat_screen_menu_events_are_meaningless():
    # Man 4 chi co duy nhat tinh nang chat — khong co menu che do nao ca.
    result = transition(ScreenRole.CHAT, ScreenState.PROMPT_CHAT_BUTTON, ScreenEvent.MENU_SELECT_INFO)
    assert result.handled is False


@pytest.mark.parametrize(
    "state",
    [
        ScreenState.STANDBY,
        ScreenState.PROMPT_CHAT_BUTTON,
        ScreenState.CHAT,
    ],
)
def test_chat_screen_cluster_reset_from_any_state(state):
    result = transition(ScreenRole.CHAT, state, ScreenEvent.CLUSTER_RESET)
    assert result.new_state == ScreenState.STANDBY
    if state == ScreenState.CHAT:
        assert EFFECT_CLOSE_CHAT_SESSION in result.effects
    else:
        assert result.effects == ()
