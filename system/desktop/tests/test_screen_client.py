import json

import pytest

from desktop.screen_client import ScreenClient


@pytest.fixture
def client():
    c = ScreenClient(4, url="ws://127.0.0.1:1/khong-dung")
    c._connected = True
    c.sent = []
    c._socket.sendTextMessage = lambda text: c.sent.append(json.loads(text))
    return c


def state(view, st="CHAT", **data):
    return {"type": "state_update", "screen_id": 4, "state": st, "view": view, "data": data}


def chat_state(session="s1", waiting=False, in_error=False, st="CHAT"):
    return state("chat", st=st, session_id=session, waiting_for_ai=waiting, in_error=in_error)


def messages(c):
    return c._model.items()


def test_starts_in_connecting_view():
    c = ScreenClient(1, url="ws://127.0.0.1:1/x")
    assert c.property("view") == "connecting"
    assert c.property("connected") is False


def test_state_update_sets_view_and_data(client):
    client.handle_message(state("standby", st="STANDBY", t0=1.0, server_now=2.0))
    assert client.property("view") == "standby"
    assert client.property("state") == "STANDBY"
    data = client.property("data")
    assert data["t0"] == 1.0
    assert "received_at" in data


def test_question_is_shown_right_away_and_input_locks(client):
    client.handle_message(chat_state())

    assert client.sendChat("  Mấy giờ khám?  ") is True

    assert messages(client) == [("user", "Mấy giờ khám?")]
    assert client.property("waitingForAi") is True
    assert client.sent[-1] == {"type": "chat_message", "screen_id": 4, "session_id": "s1", "text": "Mấy giờ khám?"}
    # Bấm gửi lần 2 khi chưa có trả lời bị chặn ngay ở giao diện.
    assert client.sendChat("câu nữa") is False
    assert len(client.sent) == 1


def test_empty_question_or_no_session_is_not_sent(client):
    assert client.sendChat("xin chào") is False  # chưa có phiên
    client.handle_message(chat_state())
    assert client.sendChat("   ") is False
    assert client.sent == []


def test_answer_for_the_current_session_is_appended(client):
    client.handle_message(chat_state())
    client.sendChat("Hỏi")
    client.handle_message({"type": "chat_message_ack", "screen_id": 4, "session_id": "s1", "role": "assistant", "text": "Đáp"})
    client.handle_message(chat_state(waiting=False))

    assert messages(client) == [("user", "Hỏi"), ("assistant", "Đáp")]
    assert client.property("waitingForAi") is False


def test_late_answer_of_an_old_session_is_dropped(client):
    client.handle_message(chat_state(session="moi"))
    client.handle_message({"type": "chat_message_ack", "screen_id": 4, "session_id": "cu", "role": "assistant", "text": "x"})
    assert messages(client) == []


def test_new_session_starts_with_empty_history(client):
    client.handle_message(chat_state(session="s1"))
    client.sendChat("Hỏi")
    client.handle_message({"type": "session_closed", "screen_id": 4, "session_id": "s1", "reason": "user_exit"})
    assert messages(client) == []

    client.handle_message(state("prompt_chat", st="PROMPT_CHAT_BUTTON"))
    client.handle_message(chat_state(session="s2"))
    assert messages(client) == []
    assert client.property("sessionId") == "s2"


def test_leaving_chat_view_clears_history_even_without_session_closed(client):
    client.handle_message(chat_state(session="s1"))
    client.sendChat("Hỏi")
    client.handle_message(state("standby", st="STANDBY"))
    assert messages(client) == []
    assert client.property("sessionId") == ""


def test_error_is_shown_until_the_next_question(client):
    client.handle_message(chat_state())
    client.handle_message({"type": "error", "screen_id": 4, "session_id": "s1", "code": "ai_timeout", "message": "Lâu quá"})
    assert client.property("errorText") == "Lâu quá"

    client.handle_message(chat_state(in_error=True))
    assert client.property("inError") is True
    assert client.property("errorText") == "Lâu quá"

    client.sendChat("Hỏi lại")
    assert client.property("errorText") == ""


def test_tier1_prompt_shows_and_ack_uses_its_session(client):
    client.handle_message(chat_state())
    client.handle_message({"type": "confirm_prompt", "screen_id": 4, "kind": "tier1_warning",
                           "session_id": "s1", "message": "?", "timeout_sec": 30})
    assert client.property("tier1Visible") is True
    assert client.property("tier1Seconds") == 30

    client.ackTier1()
    assert client.sent[-1] == {"type": "tier1_ack", "screen_id": 4, "session_id": "s1"}
    assert client.property("tier1Visible") is False

    client.ackTier1()  # bấm lần nữa không gửi thêm
    assert len(client.sent) == 1


def test_any_state_change_hides_the_tier1_prompt(client):
    client.handle_message(chat_state())
    client.handle_message({"type": "confirm_prompt", "screen_id": 4, "kind": "tier1_warning",
                           "session_id": "s1", "message": "?", "timeout_sec": 30})
    client.handle_message(chat_state())
    assert client.property("tier1Visible") is False


def test_touch_and_slide_selection_messages(client):
    client.touch("exit_chat")
    client.selectSlide("noi_quy")
    assert client.sent == [
        {"type": "touch_event", "screen_id": 4, "target": "exit_chat"},
        {"type": "select_slide", "screen_id": 4, "slide_id": "noi_quy"},
    ]


def test_nothing_is_sent_while_disconnected(client):
    client._connected = False
    client.touch("generic_wake")
    assert client.sent == []


def test_media_url_points_at_the_backend(client):
    assert client.mediaUrl("/media/a.png").startswith("http://127.0.0.1:")
    assert client.mediaUrl("/media/a.png").endswith("/media/a.png")
