from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Bang chuyen trang thai THUAN TUY cho tung loai man hinh.
# Khong asyncio, khong I/O, khong doc/ghi state ngoai — de test dong bo, khong can mock.
# Cac hieu ung nhieu-man (vd BAND_ACTIVATE phai duoc broadcast toi 1,3,5) do
# ClusterController dien giai tu "effects" tra ve, KHONG tu thuc thi o day.


class ScreenRole(str, Enum):
    PASSIVE = "PASSIVE"  # Man 1, 3, 5 — khong gan input handler, la 3 man duy nhat trinh chieu slide
    CONTROL = "CONTROL"  # Man 2 — menu dieu khien chinh
    CHAT = "CHAT"  # Man 4 — chat chuyen dung


class ScreenState(str, Enum):
    STANDBY = "STANDBY"
    MENU = "MENU"  # chi CONTROL — chon 1 trong 2 che do
    SLIDE_CONTROL = "SLIDE_CONTROL"  # chi CONTROL — bang 6 nut dieu khien slide cua man 1/3/5
    PROMPT_CHAT_BUTTON = "PROMPT_CHAT_BUTTON"  # chi role CHAT
    SLIDE_MEMBER = "SLIDE_MEMBER"  # chi PASSIVE — dang trinh chieu slide
    CHAT = "CHAT"
    CHAT_CONFIRM_SWITCH = "CHAT_CONFIRM_SWITCH"  # chi CONTROL, sub-state cua CHAT


class ScreenEvent(str, Enum):
    TOUCH_OWN = "TOUCH_OWN"  # nguoi dung cham/click truc tiep man nay
    WAKE_PAIR = "WAKE_PAIR"  # man kia (2 hoac 4) bi cham, man nay duoc "danh thuc" cung luc
    MENU_SELECT_INFO = "MENU_SELECT_INFO"
    MENU_SELECT_CHAT = "MENU_SELECT_CHAT"
    MENU_BACK = "MENU_BACK"  # tu bang dieu khien slide quay ve menu 2 che do
    CHAT_EXIT = "CHAT_EXIT"  # nguoi dung bam "Ket thuc" chu dong
    CONFIRM_YES = "CONFIRM_YES"
    CONFIRM_NO = "CONFIRM_NO"
    TIER1_TIMEOUT = "TIER1_TIMEOUT"  # tu dong dep do im lang (Tier-1 cleanup timer)
    ERROR_TIMEOUT = "ERROR_TIMEOUT"  # tu dong dep do loi mang/AI
    BAND_ACTIVATE = "BAND_ACTIVATE"  # cluster kich hoat dai slide Thong tin benh vien
    CLUSTER_RESET = "CLUSTER_RESET"  # Tier-2 timeout, dua ca cum ve Standby


EFFECT_ACTIVATE_BAND = "activate_band"  # broadcast BAND_ACTIVATE toi cac man con lai
EFFECT_OPEN_CHAT_SESSION = "open_chat_session"
EFFECT_CLOSE_CHAT_SESSION = "close_chat_session"


@dataclass(frozen=True)
class TransitionResult:
    new_state: ScreenState
    effects: tuple[str, ...] = ()
    handled: bool = True  # False = event khong co nghia voi (role, state) nay, giu nguyen state


ROLE_BY_SCREEN: dict[int, ScreenRole] = {
    1: ScreenRole.PASSIVE,
    2: ScreenRole.CONTROL,
    3: ScreenRole.PASSIVE,
    4: ScreenRole.CHAT,
    5: ScreenRole.PASSIVE,
}

CHAT_LIKE_STATES = (ScreenState.CHAT, ScreenState.CHAT_CONFIRM_SWITCH)

# 3 cach ket thuc 1 phien chat, khac nhau ve nguyen nhan nhung GIONG HET nhau ve state dich.
# Gom lai 1 cho de khong bao gio bi lech giua 3 duong (bug tung xay ra khi khai bao roi rac).
_CHAT_EXIT_EVENTS = (ScreenEvent.CHAT_EXIT, ScreenEvent.TIER1_TIMEOUT, ScreenEvent.ERROR_TIMEOUT)

_PASSIVE_TABLE: dict[tuple[ScreenState, ScreenEvent], ScreenState] = {
    (ScreenState.STANDBY, ScreenEvent.BAND_ACTIVATE): ScreenState.SLIDE_MEMBER,
}

_CONTROL_TABLE: dict[tuple[ScreenState, ScreenEvent], tuple[ScreenState, tuple[str, ...]]] = {
    (ScreenState.STANDBY, ScreenEvent.TOUCH_OWN): (ScreenState.MENU, ()),
    (ScreenState.STANDBY, ScreenEvent.WAKE_PAIR): (ScreenState.MENU, ()),
    (ScreenState.MENU, ScreenEvent.MENU_SELECT_INFO): (ScreenState.SLIDE_CONTROL, (EFFECT_ACTIVATE_BAND,)),
    (ScreenState.MENU, ScreenEvent.MENU_SELECT_CHAT): (ScreenState.CHAT, (EFFECT_OPEN_CHAT_SESSION,)),
    # Dang o bang dieu khien slide van co the mo chat — dai slide tren man 1/3/5 KHONG bi ngat
    # ("khong gian doan nen" trong dac ta).
    (ScreenState.SLIDE_CONTROL, ScreenEvent.MENU_SELECT_CHAT): (ScreenState.CHAT, (EFFECT_OPEN_CHAT_SESSION,)),
    (ScreenState.SLIDE_CONTROL, ScreenEvent.MENU_BACK): (ScreenState.MENU, ()),
    (ScreenState.CHAT, ScreenEvent.MENU_SELECT_INFO): (ScreenState.CHAT_CONFIRM_SWITCH, ()),
    (ScreenState.CHAT_CONFIRM_SWITCH, ScreenEvent.CONFIRM_YES): (
        ScreenState.SLIDE_CONTROL,
        (EFFECT_CLOSE_CHAT_SESSION, EFFECT_ACTIVATE_BAND),
    ),
    (ScreenState.CHAT_CONFIRM_SWITCH, ScreenEvent.CONFIRM_NO): (ScreenState.CHAT, ()),
}

_CHAT_SCREEN_TABLE: dict[tuple[ScreenState, ScreenEvent], tuple[ScreenState, tuple[str, ...]]] = {
    # Cham truc tiep Man 4 tu STANDBY -> vao CHAT ngay, khong qua PROMPT_CHAT_BUTTON.
    (ScreenState.STANDBY, ScreenEvent.TOUCH_OWN): (ScreenState.CHAT, (EFFECT_OPEN_CHAT_SESSION,)),
    (ScreenState.STANDBY, ScreenEvent.WAKE_PAIR): (ScreenState.PROMPT_CHAT_BUTTON, ()),
    # Man 4 khong tham gia dai slide — no chi hien nut "Cham de chat" khi cum thuc day.
    (ScreenState.STANDBY, ScreenEvent.BAND_ACTIVATE): (ScreenState.PROMPT_CHAT_BUTTON, ()),
    (ScreenState.PROMPT_CHAT_BUTTON, ScreenEvent.TOUCH_OWN): (ScreenState.CHAT, (EFFECT_OPEN_CHAT_SESSION,)),
}


def _chat_exit_target(role: ScreenRole) -> ScreenState:
    """Ket thuc chat -> ve dung "man hinh chon che do ban dau" cua tung vai tro, KHONG ve thang
    Standby — Tier-2 moi la tang dua ca cum di ngu.

    descryption.txt muc 3 noi ro dich den: "tu quay ve trang thai ban dau (man 2 co 2 o la che do
    trinh chieu va che do chat con man 4 chi co 1 o ghi che do chat)". Vi vay man 2 LUON ve MENU,
    khong phu thuoc dai slide dang chay hay khong — man 1/3/5 van chieu tiep, khong bi dong den.
    """
    return ScreenState.MENU if role is ScreenRole.CONTROL else ScreenState.PROMPT_CHAT_BUTTON


def transition(role: ScreenRole, state: ScreenState, event: ScreenEvent) -> TransitionResult:
    """(role, state, event) -> TransitionResult. Ham thuan tuy, khong side-effect."""

    # CLUSTER_RESET va nhom su kien ket thuc chat ap dung dong nhat cho moi vai tro nen xu ly
    # truoc, khong nhan ban vao tung bang tra cuu.
    if event is ScreenEvent.CLUSTER_RESET:
        effects = (EFFECT_CLOSE_CHAT_SESSION,) if state in CHAT_LIKE_STATES else ()
        return TransitionResult(ScreenState.STANDBY, effects)

    if event in _CHAT_EXIT_EVENTS:
        if state in CHAT_LIKE_STATES:
            return TransitionResult(_chat_exit_target(role), (EFFECT_CLOSE_CHAT_SESSION,))
        return TransitionResult(state, (), handled=False)

    if role is ScreenRole.PASSIVE:
        found = _PASSIVE_TABLE.get((state, event))
        if found is not None:
            return TransitionResult(found, ())
        return TransitionResult(state, (), handled=False)

    table = _CONTROL_TABLE if role is ScreenRole.CONTROL else _CHAT_SCREEN_TABLE
    found = table.get((state, event))
    if found is not None:
        new_state, effects = found
        return TransitionResult(new_state, effects)
    return TransitionResult(state, (), handled=False)
