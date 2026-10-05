import asyncio
import shutil
import subprocess

import pytest

from app.state import video_slicer as vs_module
from app.state.video_slicer import VideoSlicer, build_slice_command

imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")

WIDTH, HEIGHT = 192, 32


def _make_video(path, pattern="testsrc2"):
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"{pattern}=size={WIDTH}x{HEIGHT}:rate=10:duration=1",
            "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def source(tmp_path):
    """Video thu 192x32, 1 giay — hinh testsrc2 co mau khac nhau theo chieu ngang."""
    return _make_video(tmp_path / "nguon.mp4")


def _first_frame(path):
    gen = imageio_ffmpeg.read_frames(str(path))
    meta = next(gen)
    frame = next(gen)
    gen.close()
    return meta["size"], frame


def _crop(frame: bytes, x: int, w: int) -> bytes:
    out = bytearray()
    for row in range(HEIGHT):
        start = (row * WIDTH + x) * 3
        out += frame[start:start + w * 3]
    return bytes(out)


def _diff(a: bytes, b: bytes) -> float:
    return sum(abs(p - q) for p, q in zip(a, b, strict=True)) / len(a)


def test_command_splits_once_and_crops_left_to_right(tmp_path):
    outputs = [tmp_path / f"o{i}.mp4" for i in range(3)]
    cmd = build_slice_command("ffmpeg", tmp_path / "in.mp4", outputs)

    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.startswith("[0:v]split=3[s0][s1][s2]")
    for i in range(3):
        assert f"[s{i}]crop=floor(iw/3/2)*2:ih:floor(iw*{i}/3):0[o{i}]" in graph
    assert [a for a in cmd if a.endswith(".mp4")][1:] == [str(o) for o in outputs]


def test_not_ready_until_the_done_marker_exists(source, tmp_path):
    slicer = VideoSlicer(source, tmp_path / "cache")
    assert slicer.ready(3) is False
    assert slicer.slice_path(3, 0) is None


async def test_slices_are_the_matching_parts_of_the_source(source, tmp_path):
    ready_calls = []

    async def on_ready(n):
        ready_calls.append(n)

    slicer = VideoSlicer(source, tmp_path / "cache", on_ready=on_ready)
    slicer.ensure(3)
    assert slicer.working_on == 3
    await slicer._task

    assert ready_calls == [3]
    assert slicer.ready(3) is True
    assert slicer.slice_path(3, 3) is None

    _, full = _first_frame(source)
    parts = [_crop(full, i * 64, 64) for i in range(3)]
    for i in range(3):
        size, frame = _first_frame(slicer.slice_path(3, i))
        assert size == (64, HEIGHT)
        # Lat i phai giong phan i cua video goc hon han moi phan khac -> dung thu tu trai -> phai.
        own = _diff(frame, parts[i])
        others = [_diff(frame, parts[j]) for j in range(3) if j != i]
        assert own < 8
        assert all(own * 3 < d for d in others)


async def test_ready_slices_are_not_cut_again(source, tmp_path):
    slicer = VideoSlicer(source, tmp_path / "cache")
    slicer.ensure(2)
    await slicer._task

    slicer.ensure(2)
    assert slicer.working_on is None


async def test_one_screen_needs_no_slices(source, tmp_path):
    slicer = VideoSlicer(source, tmp_path / "cache")
    slicer.ensure(1)
    assert slicer.working_on is None


async def test_changing_the_source_video_invalidates_old_slices(source, tmp_path):
    slicer = VideoSlicer(source, tmp_path / "cache")
    slicer.ensure(2)
    await slicer._task
    old_dir = slicer.slice_path(2, 0).parent

    _make_video(source, pattern="smptebars")  # chep de video khac, cung ten file
    assert slicer.ready(2) is False

    slicer.ensure(2)
    await slicer._task
    assert slicer.ready(2) is True
    # Lat cua video cu bi don di, khong de day o dia.
    assert not old_dir.exists()


async def test_slices_survive_copying_the_whole_folder_elsewhere(source, tmp_path):
    cache = tmp_path / "cache"
    slicer = VideoSlicer(source, cache)
    slicer.ensure(2)
    await slicer._task

    # Chep sang cho khac (vd sang thu muc ban dong goi): duong dan va ngay sua co the doi,
    # noi dung giu nguyen -> dung lai duoc lat da cat, khong phai cat lai.
    moved = tmp_path / "noi_khac" / "video.mp4"
    moved.parent.mkdir()
    shutil.copyfile(source, moved)
    assert VideoSlicer(moved, cache).ready(2) is True


async def test_new_layout_cancels_the_cut_in_progress(source, tmp_path, monkeypatch):
    slicer = VideoSlicer(source, tmp_path / "cache")
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(n):
        started.set()
        await release.wait()

    monkeypatch.setattr(slicer, "_run", slow_run)
    slicer.ensure(5)
    first = slicer._task
    await started.wait()

    monkeypatch.setattr(slicer, "_run", VideoSlicer._run.__get__(slicer))
    slicer.ensure(3)
    await asyncio.sleep(0)

    assert first.cancelled()
    assert slicer.working_on == 3
    await slicer._task
    assert slicer.ready(3) is True
    assert slicer.ready(5) is False


async def test_missing_ffmpeg_leaves_the_full_video_in_use(source, tmp_path, monkeypatch):
    monkeypatch.setattr(vs_module, "_ffmpeg_exe", lambda: None)
    slicer = VideoSlicer(source, tmp_path / "cache")

    slicer.ensure(3)
    await slicer._task

    assert slicer.ready(3) is False


async def test_missing_source_is_not_an_error(tmp_path):
    slicer = VideoSlicer(tmp_path / "khong_co.mp4", tmp_path / "cache")

    slicer.ensure(3)
    await slicer._task

    assert slicer.ready(3) is False
