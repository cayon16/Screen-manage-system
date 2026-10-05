from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QEventPoint, QInputDevice, QMouseEvent, QPointingDevice, QTouchEvent

from desktop.window_manager import _is_press, _WakeOnPress

TOUCH = QPointingDevice("man-cam-ung-thu", 9001, QInputDevice.DeviceType.TouchScreen,
                        QPointingDevice.PointerType.Finger, QInputDevice.Capability.Position, 10, 0)


def touch(kind, *states):
    points = [QEventPoint(i, state, QPointF(10, 10), QPointF(10, 10)) for i, state in enumerate(states)]
    return QTouchEvent(kind, TOUCH, Qt.KeyboardModifier.NoModifier, points)


P = QEventPoint.State.Pressed
S = QEventPoint.State.Stationary
R = QEventPoint.State.Released
U = QEventPoint.State.Updated


def test_touch_begin_is_a_press():
    assert _is_press(touch(QEvent.Type.TouchBegin, P))


def test_new_finger_inside_an_update_is_a_press():
    # Màn 2 đang có ngón tay (Stationary), màn 4 vừa bị chạm → Qt gửi TouchUpdate, không phải TouchBegin.
    assert _is_press(touch(QEvent.Type.TouchUpdate, P))
    assert _is_press(touch(QEvent.Type.TouchUpdate, S, P))


def test_moving_or_lifting_is_not_a_press():
    assert not _is_press(touch(QEvent.Type.TouchUpdate, U))
    assert not _is_press(touch(QEvent.Type.TouchUpdate, S, R))
    assert not _is_press(touch(QEvent.Type.TouchEnd, R))


def test_mouse_press_counts_but_release_does_not():
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(1, 1), QPointF(1, 1), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(1, 1), QPointF(1, 1), Qt.MouseButton.LeftButton,
                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    assert _is_press(press)
    assert not _is_press(release)


class FakeClient:
    def __init__(self):
        self.sent = []

    def touch(self, target):
        self.sent.append(target)


def test_filter_sends_one_wake_per_touch_and_never_swallows_events(monkeypatch):
    client = FakeClient()
    wake = _WakeOnPress(client)
    clock = iter([100.0, 100.05, 100.5])
    monkeypatch.setattr("desktop.window_manager.time.monotonic", lambda: next(clock))

    assert wake.eventFilter(None, touch(QEvent.Type.TouchBegin, P)) is False
    # cùng lần chạm đó đến thêm dưới dạng chuột giả lập → không gửi lần 2
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(1, 1), QPointF(1, 1), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    assert wake.eventFilter(None, press) is False
    assert wake.eventFilter(None, touch(QEvent.Type.TouchUpdate, S, P)) is False

    assert client.sent == ["generic_wake", "generic_wake"]
