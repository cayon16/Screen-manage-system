import json

import pytest

from app.config import SLIDE_SCREENS
from app.state.slide_band import SlideBand


def test_real_manifest_gives_exactly_two_slides_per_passive_screen():
    band = SlideBand.load()

    buttons = band.buttons()
    assert len(buttons) == 6  # dung con so trong descryption.txt
    for screen_id in SLIDE_SCREENS:
        assert len([b for b in buttons if b["screen_id"] == screen_id]) == 2


def test_default_slide_is_the_first_one_of_each_screen():
    band = SlideBand.load()
    for screen_id in SLIDE_SCREENS:
        first_of_screen = next(b for b in band.buttons() if b["screen_id"] == screen_id)
        assert band.current_slide(screen_id).id == first_of_screen["slide_id"]


def test_selecting_a_slide_only_moves_the_screen_that_owns_it():
    band = SlideBand.load()
    before = {sid: band.current_slide(sid).id for sid in SLIDE_SCREENS}

    target = next(b for b in band.buttons() if b["screen_id"] == 3 and b["slide_id"] != before[3])
    changed = band.select(target["slide_id"])

    assert changed == 3
    assert band.current_slide(3).id == target["slide_id"]
    for sid in SLIDE_SCREENS:
        if sid != 3:
            assert band.current_slide(sid).id == before[sid]


def test_unknown_slide_id_changes_nothing():
    band = SlideBand.load()
    before = {sid: band.current_slide(sid).id for sid in SLIDE_SCREENS}

    assert band.select("khong_co_that") is None
    assert {sid: band.current_slide(sid).id for sid in SLIDE_SCREENS} == before


def _manifest(tmp_path, screen1_slides) -> tuple:
    """Manifest hop le toi thieu; man 1 dung noi dung do test truyen vao."""
    screens = {
        str(sid): [
            {"id": f"a_{sid}", "title": "A", "bullets": []},
            {"id": f"b_{sid}", "title": "B", "bullets": []},
        ]
        for sid in SLIDE_SCREENS
    }
    screens["1"] = screen1_slides
    path = tmp_path / "slides.json"
    path.write_text(json.dumps({"screens": screens}), encoding="utf-8")
    media = tmp_path / "media"
    media.mkdir(exist_ok=True)
    return path, media


# ---------- slide anh / video ----------


def test_image_and_video_slides_expose_an_http_path_not_a_disk_path(tmp_path):
    path, media = _manifest(
        tmp_path,
        [
            {"id": "anh", "kind": "image", "title": "Nội quy", "src": "noi_quy.png"},
            {"id": "phim", "kind": "video", "title": "Giới thiệu", "src": "gt.mp4"},
        ],
    )
    (media / "noi_quy.png").write_bytes(b"fake-png")
    (media / "gt.mp4").write_bytes(b"fake-mp4")

    band = SlideBand.load(path, media)

    assert band.current_slide(1).as_dict() == {
        "id": "anh",
        "screen_id": 1,
        "kind": "image",
        "title": "Nội quy",
        "src": "/media/noi_quy.png",
    }
    band.select("phim")
    assert band.current_slide(1).as_dict()["src"] == "/media/gt.mp4"


def test_text_slides_do_not_carry_a_src(tmp_path):
    path, media = _manifest(
        tmp_path, [{"id": "chu", "title": "T", "subtitle": "S", "bullets": ["x"]}]
    )
    band = SlideBand.load(path, media)
    data = band.current_slide(1).as_dict()
    assert data["kind"] == "text"
    assert "src" not in data
    assert data["bullets"] == ["x"]


def test_media_slide_without_src_is_rejected(tmp_path):
    path, media = _manifest(tmp_path, [{"id": "anh", "kind": "image", "title": "A"}])
    with pytest.raises(ValueError, match="thieu 'src'"):
        SlideBand.load(path, media)


def test_unknown_kind_is_rejected(tmp_path):
    path, media = _manifest(tmp_path, [{"id": "x", "kind": "pdf", "title": "A", "src": "a.pdf"}])
    with pytest.raises(ValueError, match="khong hop le"):
        SlideBand.load(path, media)


@pytest.mark.parametrize("bad_src", ["../secret.png", "sub/anh.png", r"sub\anh.png"])
def test_src_must_be_a_bare_filename(tmp_path, bad_src):
    # 'src' di thang vao URL /media/{filename}; cho phep duong dan o day la mo duong cho
    # nguoi sua manifest vo tinh tro ra ngoai thu muc media.
    path, media = _manifest(tmp_path, [{"id": "x", "kind": "image", "title": "A", "src": bad_src}])
    with pytest.raises(ValueError, match="TEN FILE"):
        SlideBand.load(path, media)


def test_missing_media_file_warns_but_still_starts(tmp_path, caplog):
    # Thieu 1 file noi dung khong duoc phep lam ca 5 man hinh cua benh vien khong khoi dong duoc.
    path, media = _manifest(
        tmp_path, [{"id": "anh", "kind": "image", "title": "A", "src": "chua_co.png"}]
    )
    band = SlideBand.load(path, media)
    assert band.current_slide(1).id == "anh"


def test_duplicate_slide_ids_are_rejected_at_load_time(tmp_path):
    # Bang dieu khien chi gui ve 1 slide_id — id trung nhau giua 2 man se lam bam nut nay
    # nhay noi dung sang man khac. Phai chan ngay luc doc file, khong de chay roi moi phat hien.
    manifest = {
        "screens": {
            str(sid): [
                {"id": "trung_id", "title": "A", "bullets": []},
                {"id": f"rieng_{sid}", "title": "B", "bullets": []},
            ]
            for sid in SLIDE_SCREENS
        }
    }
    path = tmp_path / "slides.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="trung"):
        SlideBand.load(path)


def test_missing_screen_in_manifest_is_rejected(tmp_path):
    manifest = {"screens": {"1": [{"id": "a", "title": "A", "bullets": []}]}}
    path = tmp_path / "slides.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="thieu noi dung slide"):
        SlideBand.load(path)
