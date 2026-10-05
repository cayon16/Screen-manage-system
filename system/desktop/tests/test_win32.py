import ctypes
import sys
from ctypes import wintypes

import pytest
from PySide6.QtCore import QByteArray

from desktop import win32


def test_rect_match_allows_one_pixel_of_rounding():
    assert win32.rect_matches((1920, 0, 1920, 1080), (1920, 0, 1920, 1080))
    assert win32.rect_matches((1919, 0, 1921, 1080), (1920, 0, 1920, 1080))


def test_rect_mismatch_is_detected():
    # Lỗi của bản cũ: cửa sổ to gấp rưỡi màn ở scale 150%.
    assert not win32.rect_matches((0, 0, 2880, 1620), (0, 0, 1920, 1080))
    assert not win32.rect_matches((1920, 0, 1920, 1080), (0, 0, 1920, 1080))
    assert not win32.rect_matches(None, (0, 0, 1920, 1080))


def test_helpers_ignore_missing_window():
    assert win32.window_rect(0) is None
    assert win32.monitor_of_window(0) == 0
    assert win32.force_rect(0, (0, 0, 1, 1), True) is False
    assert win32.set_topmost(0, True) is False
    win32.disable_touch_feedback(0)


def _hotkey_message(hotkey_id: int):
    msg = wintypes.MSG()
    msg.message = win32.WM_HOTKEY
    msg.wParam = hotkey_id
    return msg


@pytest.mark.skipif(sys.platform != "win32", reason="phím tắt toàn cục chỉ có trên Windows")
def test_hotkey_message_runs_its_action():
    hotkeys = win32.GlobalHotkeys()
    calls = []
    hotkeys._actions[0xB000] = lambda: calls.append("M")
    msg = _hotkey_message(0xB000)

    handled, _ = hotkeys.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(msg))

    assert handled is True
    assert calls == ["M"]


@pytest.mark.skipif(sys.platform != "win32", reason="phím tắt toàn cục chỉ có trên Windows")
def test_other_messages_and_unknown_hotkeys_pass_through():
    hotkeys = win32.GlobalHotkeys()
    hotkeys._actions[0xB000] = lambda: pytest.fail("không được gọi")
    other = wintypes.MSG()
    other.message = 0x0100  # WM_KEYDOWN
    unknown = _hotkey_message(0xB001)

    assert hotkeys.nativeEventFilter(QByteArray(b"windows_generic_MSG"), ctypes.addressof(other))[0] is False
    assert hotkeys.nativeEventFilter(QByteArray(b"windows_generic_MSG"), ctypes.addressof(unknown))[0] is False
    assert hotkeys.nativeEventFilter(QByteArray(b"xcb_generic_event_t"), 0)[0] is False


@pytest.mark.skipif(sys.platform != "win32", reason="phím tắt toàn cục chỉ có trên Windows")
def test_a_failing_action_does_not_break_the_event_loop():
    hotkeys = win32.GlobalHotkeys()

    def boom():
        raise RuntimeError("lỗi thử")

    hotkeys._actions[0xB000] = boom
    msg = _hotkey_message(0xB000)
    assert hotkeys.nativeEventFilter(QByteArray(b"windows_generic_MSG"), ctypes.addressof(msg))[0] is True


@pytest.mark.skipif(sys.platform != "win32", reason="phím tắt toàn cục chỉ có trên Windows")
def test_register_and_unregister_a_real_hotkey():
    hotkeys = win32.GlobalHotkeys()
    # Tổ hợp ít ai dùng; nếu máy đã có chương trình giữ nó thì register trả False — vẫn không lỗi.
    combo = hotkeys.register("J", lambda: None)
    assert combo in ("Ctrl+Shift+J", "Ctrl+Alt+Shift+J", "")
    hotkeys.unregister_all()
    assert hotkeys._actions == {}
