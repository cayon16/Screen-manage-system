import pytest
from PySide6.QtMultimedia import QMediaPlayer

from desktop import standby_sync
from desktop.standby_sync import (
    HARD_SEEK_SEC,
    RATE_MAX,
    RATE_MIN,
    StandbySync,
    correction,
    drift,
    target_time,
)


def test_target_wraps_around_the_video_length():
    assert target_time(now=1000.0, t0=990.0, duration=600.0) == pytest.approx(10.0)
    assert target_time(now=1000.0, t0=390.0, duration=600.0) == pytest.approx(10.0)


def test_drift_is_measured_around_the_loop():
    # Video vừa lặp về đầu (0.1 s) trong khi mốc chung còn ở cuối (599.9 s): chỉ lệch 0.2 s.
    assert drift(target=599.9, current=0.1, duration=600.0) == pytest.approx(-0.2)
    assert drift(target=0.1, current=599.9, duration=600.0) == pytest.approx(0.2)


def test_large_drift_jumps_straight_to_the_target():
    seek, rate = correction(target=10.0, current=10.0 + HARD_SEEK_SEC + 0.1, duration=600.0)
    assert seek == 10.0 and rate == 1.0


def test_in_sync_plays_at_normal_speed():
    assert correction(target=10.0, current=10.01, duration=600.0) == (None, 1.0)


def test_small_drift_nudges_the_speed_in_the_right_direction():
    _, behind = correction(target=10.2, current=10.0, duration=600.0)
    _, ahead = correction(target=10.0, current=10.2, duration=600.0)
    assert 1.0 < behind <= RATE_MAX
    assert RATE_MIN <= ahead < 1.0


def test_small_drift_across_the_loop_point_is_not_a_jump():
    seek, rate = correction(target=0.05, current=599.95, duration=600.0)
    assert seek is None
    assert rate > 1.0


class FakePlayer:
    """Đứng thay QMediaPlayer: chỉ ghi lại lệnh tua / đổi tốc độ."""

    def __init__(self, position_s, duration_s=600.0):
        self.pos_ms = int(position_s * 1000)
        self.duration_ms = int(duration_s * 1000)
        self.rate = 1.0
        self.seeks = []

    def duration(self):
        return self.duration_ms

    def isSeekable(self):
        return True

    def playbackState(self):
        return QMediaPlayer.PlaybackState.PlayingState

    def play(self):
        pass

    def position(self):
        return self.pos_ms

    def setPosition(self, ms):
        self.seeks.append(ms)
        self.pos_ms = ms

    def playbackRate(self):
        return self.rate

    def setPlaybackRate(self, rate):
        self.rate = rate


def _sync_with(player, now, target_s):
    sync = StandbySync()
    sync._player = player
    sync._t0 = now - target_s
    sync._offset = 0.0
    return sync


def test_one_stale_reading_does_not_jump(monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(standby_sync.time, "time", lambda: now)
    player = FakePlayer(position_s=9.0)
    sync = _sync_with(player, now, target_s=10.0)

    sync._tick()
    assert player.seeks == []

    sync._tick()
    assert player.seeks == [10000]


def test_a_good_reading_resets_the_jump_counter(monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(standby_sync.time, "time", lambda: now)
    player = FakePlayer(position_s=9.0)
    sync = _sync_with(player, now, target_s=10.0)

    sync._tick()
    player.pos_ms = 10000
    sync._tick()
    player.pos_ms = 9000
    sync._tick()
    assert player.seeks == []


def test_small_drift_only_changes_speed(monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(standby_sync.time, "time", lambda: now)
    player = FakePlayer(position_s=9.9)
    sync = _sync_with(player, now, target_s=10.0)

    sync._tick()
    assert player.seeks == []
    assert player.rate > 1.0
