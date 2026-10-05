from desktop.layout import Monitor
from desktop.monitors import ScreenEntry, touch_problem


def _entry(handle: int, x: int, primary: bool = False, touch: bool = False) -> ScreenEntry:
    return ScreenEntry(
        monitor=Monitor(key=f"D{handle}", x=x, y=0, width=1920, height=1080, primary=primary, touch=touch),
        screen=None,
        scale_percent=100,
        handle=handle,
    )


WALL = [_entry(11, 0, primary=True), _entry(12, 1920), _entry(13, 3840), _entry(14, 5760), _entry(15, 7680)]


def test_no_touch_device_is_not_a_problem():
    assert touch_problem([], WALL) is None


def test_two_touch_screens_on_two_monitors_is_fine():
    assert touch_problem([12, 14], WALL) is None


def test_touch_device_not_mapped_to_any_monitor_is_reported():
    problem = touch_problem([0, 14], WALL)
    assert problem and "1/2" in problem and "Tablet PC Settings" in problem


def test_two_touch_devices_on_the_same_monitor_are_reported():
    problem = touch_problem([12, 12], WALL)
    assert problem and "chỉ gắn vào 1 màn" in problem


def test_all_touch_on_primary_is_flagged_for_checking():
    # Dấu hiệu điển hình của việc chưa chạy Tablet PC Settings: Windows dồn cảm ứng vào màn chính.
    assert "màn chính" in touch_problem([11], WALL)


def test_single_touch_monitor_setup_is_fine():
    assert touch_problem([11], [_entry(11, 0, primary=True)]) is None


def test_entry_rect_is_physical_monitor_box():
    assert _entry(13, 3840).rect == (3840, 0, 1920, 1080)
