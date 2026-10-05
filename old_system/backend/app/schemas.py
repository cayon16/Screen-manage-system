from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

# Giao thuc WebSocket giua backend va 5 trinh duyet.
#
# Nguyen tac: KHONG khai bao truoc truong/loai message "de danh cho sau nay". Moi thu o day
# deu dang duoc it nhat 1 phia dung that; thua 1 truong la thua 1 thu de hieu nham va de lech
# giua backend voi frontend.

# ============ Client -> Server ============


class TouchEventMsg(BaseModel):
    type: Literal["touch_event"] = "touch_event"
    screen_id: int
    target: str


class ChatMessageMsg(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    screen_id: int
    session_id: str
    text: str


class Tier1AckMsg(BaseModel):
    """Nguoi dung bam "Toi van o day" trong hop canh bao im lang."""

    type: Literal["tier1_ack"] = "tier1_ack"
    screen_id: int
    session_id: str


class SelectSlideMsg(BaseModel):
    """Man 2 bam 1 trong 6 nut cua bang dieu khien trinh chieu."""

    type: Literal["select_slide"] = "select_slide"
    screen_id: int
    slide_id: str


ClientMessage = Annotated[
    Union[TouchEventMsg, ChatMessageMsg, Tier1AckMsg, SelectSlideMsg],
    Field(discriminator="type"),
]

_client_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: dict[str, Any]) -> ClientMessage:
    return _client_adapter.validate_python(raw)


# ============ Man quan ly -> Server ============


class AdminCommandMsg(BaseModel):
    type: Literal["admin_command"] = "admin_command"
    action: Literal["select_slide", "force_standby", "blackout_on", "blackout_off", "reset", "refresh"]
    slide_id: str | None = None


class LayoutDisplay(BaseModel):
    role: int
    wall_index: int


class LayoutRequest(BaseModel):
    """Than cua POST /api/layout — app Qt bao bo cuc man thuc te."""

    displays: list[LayoutDisplay]


# ============ Server -> Client ============


class StateUpdateMsg(BaseModel):
    """Message chinh: man hinh nay dang o trang thai nao va can ve gi."""

    type: Literal["state_update"] = "state_update"
    screen_id: int
    state: str
    view: str
    data: dict[str, Any] = Field(default_factory=dict)


class ChatMessageAckMsg(BaseModel):
    type: Literal["chat_message_ack"] = "chat_message_ack"
    screen_id: int
    session_id: str
    role: Literal["assistant"]
    text: str


class ConfirmPromptMsg(BaseModel):
    type: Literal["confirm_prompt"] = "confirm_prompt"
    screen_id: int
    kind: Literal["mode_switch", "tier1_warning"]
    # Chi dung cho kind="tier1_warning": client phai gui lai dung session_id trong tier1_ack,
    # tranh ack nham cho 1 phien da dong va vua duoc thay bang phien moi.
    session_id: str | None = None
    message: str
    # Chi co voi kind="tier1_warning": so giay con lai truoc khi tu ket thuc doan chat.
    timeout_sec: int | None = None


class ErrorMsg(BaseModel):
    type: Literal["error"] = "error"
    screen_id: int
    session_id: str
    code: str
    message: str


class SessionClosedMsg(BaseModel):
    type: Literal["session_closed"] = "session_closed"
    screen_id: int
    session_id: str
    reason: Literal[
        "user_exit",
        "tier1_timeout",
        "error_timeout",
        "mode_switch",
        "cluster_reset",
        "blackout",
        "system_reset",
        "screen_removed",
    ]


ServerMessage = Union[StateUpdateMsg, ChatMessageAckMsg, ConfirmPromptMsg, ErrorMsg, SessionClosedMsg]


# ============ Server -> Man quan ly ============


class AdminSnapshotMsg(BaseModel):
    """Toan canh he thong cho man quan ly. Gui lai nguyen goi moi khi co thay doi — du lieu nho,
    gui ca goi don gian hon nhieu so voi tinh phan chenh lech."""

    type: Literal["admin_snapshot"] = "admin_snapshot"
    blackout: bool
    started_at: float
    wall_count: int
    screens: list[dict[str, Any]]
    slides: list[dict[str, Any]]
    stats: dict[str, Any]
