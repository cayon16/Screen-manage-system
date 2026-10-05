import pytest

from desktop.layout import Monitor, assign


def _wall(spec: str, primary_at: int = 0) -> list[Monitor]:
    """'PTP' = trái → phải: màn thường (P), màn cảm ứng (T). Cố tình trả về lộn thứ tự để kiểm
    hàm tự xếp theo toạ độ chứ không theo thứ tự Windows liệt kê."""
    monitors = [
        Monitor(
            key=f"D{i}", x=i * 1920, y=0, width=1920, height=1080,
            primary=(i == primary_at), touch=(c == "T"),
        )
        for i, c in enumerate(spec)
    ]
    return list(reversed(monitors))


def _roles(assignment) -> list[int]:
    """Vai trò của các màn hiển thị theo thứ tự trái → phải."""
    return [d.role for d in assignment.displays]


def test_no_monitor_means_nothing_to_show():
    a = assign([])
    assert a.management is None and a.displays == ()


@pytest.mark.parametrize(
    "spec, roles",
    [
        ("P", [1]),
        ("PP", [1, 2]),
        ("PPP", [1, 2, 3]),
        ("PPPP", [1, 2, 3, 4]),
        ("PPPPP", [1, 2, 3, 4, 5]),
    ],
)
def test_without_touch_screens_roles_count_left_to_right(spec, roles):
    a = assign(_wall(spec))
    assert a.management is None
    assert _roles(a) == roles


@pytest.mark.parametrize(
    "spec, roles",
    [
        ("T", [2]),
        ("PT", [1, 2]),
        ("TP", [2, 1]),
        ("PTP", [1, 2, 3]),
        ("TPP", [2, 1, 3]),
        ("PTPTP", [1, 2, 3, 4, 5]),
        ("TTPPP", [2, 4, 1, 3, 5]),
        ("PPPTT", [1, 3, 5, 2, 4]),
        ("PTT", [1, 2, 4]),
        ("PP T P".replace(" ", ""), [1, 3, 2, 5]),
    ],
)
def test_touch_screens_take_2_and_4_plain_screens_take_1_3_5(spec, roles):
    assert _roles(assign(_wall(spec))) == roles


def test_extra_touch_screen_takes_the_smallest_free_number():
    # 3 màn cảm ứng: 2 màn đầu nhận 2 và 4, màn thứ 3 nhận số trống nhỏ nhất là 1.
    assert _roles(assign(_wall("TTT"))) == [2, 4, 1]


def test_extra_plain_screens_fill_the_touch_numbers_when_touch_is_missing():
    # 1 cảm ứng + 4 thường: thường nhận 1, 3, 5, màn thường thứ 4 nhận số trống còn lại là 4.
    assert _roles(assign(_wall("PPTPP"))) == [1, 3, 2, 5, 4]


def test_wall_index_is_left_to_right_position_not_role():
    a = assign(_wall("TPP"))
    assert [(d.monitor.key, d.role, d.wall_index) for d in a.displays] == [
        ("D0", 2, 0), ("D1", 1, 1), ("D2", 3, 2),
    ]
    assert a.as_layout_request() == {
        "displays": [
            {"role": 2, "wall_index": 0},
            {"role": 1, "wall_index": 1},
            {"role": 3, "wall_index": 2},
        ]
    }


def test_five_monitors_including_the_main_pc_all_become_displays():
    a = assign(_wall("PPPPP", primary_at=0))
    assert a.management is None
    assert len(a.displays) == 5


def test_six_monitors_turn_the_primary_into_the_management_screen():
    a = assign(_wall("PPTPTP", primary_at=0))
    assert a.management.key == "D0"
    # 5 màn còn lại: P T P T P → 1 2 3 4 5, video chờ bắt đầu từ màn D1.
    assert _roles(a) == [1, 2, 3, 4, 5]
    assert a.displays[0].monitor.key == "D1"


def test_management_screen_can_sit_in_the_middle_of_the_row():
    a = assign(_wall("PPPPPP", primary_at=2))
    assert a.management.key == "D2"
    assert [d.monitor.key for d in a.displays] == ["D0", "D1", "D3", "D4", "D5"]
    assert [d.wall_index for d in a.displays] == [0, 1, 2, 3, 4]


def test_touch_primary_still_becomes_management_when_there_are_six():
    a = assign(_wall("TPPPPP", primary_at=0))
    assert a.management.key == "D0"
    assert _roles(a) == [1, 2, 3, 4, 5]


def test_seventh_monitor_is_left_unused():
    a = assign(_wall("PPPPPPP", primary_at=0))
    assert a.management.key == "D0"
    assert _roles(a) == [1, 2, 3, 4, 5]
    assert [m.key for m in a.unused] == ["D6"]
    # Màn không dùng không được chiếm chỗ trong dãy video chờ.
    assert [d.wall_index for d in a.displays] == [0, 1, 2, 3, 4]


def test_unused_monitor_between_used_ones_does_not_leave_a_gap_in_the_wall():
    # Quản lý = D0; còn lại T T T P P P → cảm ứng 2,4, thường 1,3,5, màn cảm ứng thứ 3 hết số.
    a = assign(_wall("PTTTPPP", primary_at=0))
    assert [m.key for m in a.unused] == ["D3"]
    assert [(d.monitor.key, d.role) for d in a.displays] == [
        ("D1", 2), ("D2", 4), ("D4", 1), ("D5", 3), ("D6", 5),
    ]
    assert [d.wall_index for d in a.displays] == [0, 1, 2, 3, 4]


def test_missing_primary_flag_falls_back_to_leftmost():
    monitors = [
        Monitor(key=f"D{i}", x=i * 100, y=0, width=100, height=100) for i in range(6)
    ]
    assert assign(monitors).management.key == "D0"


def test_monitors_with_negative_coordinates_sort_correctly():
    # Màn đặt bên trái màn Primary có toạ độ x âm.
    monitors = [
        Monitor(key="chinh", x=0, y=0, width=1920, height=1080, primary=True),
        Monitor(key="trai", x=-1920, y=0, width=1920, height=1080),
    ]
    a = assign(monitors)
    assert [(d.monitor.key, d.role) for d in a.displays] == [("trai", 1), ("chinh", 2)]

