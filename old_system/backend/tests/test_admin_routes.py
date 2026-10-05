import pytest
from starlette.testclient import TestClient

from app import main as main_module
from app.main import app
from app.state.video_slicer import VideoSlicer


@pytest.fixture(autouse=True)
def quiet_app(monkeypatch, tmp_path):
    # Nguoi dang ngoi may se lam "thao tac may chu" chen snapshot bat ngo vao giua test; con cat
    # video that thi mat vai phut. Ca hai khong lien quan toi cac route dang kiem.
    monkeypatch.setattr(main_module, "HOST_ACTIVITY_ENABLED", False)
    monkeypatch.setattr(VideoSlicer, "ensure", lambda self, n: None)
    # Khong dung cache lat video that cua may (co the da cat san) — ket qua test phai co dinh.
    monkeypatch.setattr(main_module, "STANDBY_SLICE_CACHE_DIR", tmp_path / "slices")


def _recv_until(ws, predicate, limit: int = 10) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("Khong nhan duoc message mong doi")


def test_admin_socket_gets_a_snapshot_right_away():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/admin") as admin:
            snap = admin.receive_json()
            assert snap["type"] == "admin_snapshot"
            assert snap["wall_count"] == 5
            assert len(snap["screens"]) == 5


def test_posted_layout_reaches_the_controller():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/admin") as admin:
            admin.receive_json()

            resp = client.post(
                "/api/layout",
                json={"displays": [{"role": 2, "wall_index": 0}, {"role": 1, "wall_index": 1},
                                   {"role": 3, "wall_index": 2}]},
            )
            assert resp.status_code == 200
            assert resp.json()["wall_count"] == 3

            snap = _recv_until(admin, lambda m: m["wall_count"] == 3)
            active = {s["role"] for s in snap["screens"] if s["active"]}
            assert active == {1, 2, 3}


def test_invalid_layout_is_refused_with_a_reason():
    with TestClient(app) as client:
        resp = client.post(
            "/api/layout",
            json={"displays": [{"role": 1, "wall_index": 0}, {"role": 1, "wall_index": 1}]},
        )
        assert resp.status_code == 400
        assert "trung" in resp.json()["error"]

        assert client.post("/api/layout", json={"displays": "sai"}).status_code == 422


def test_admin_blackout_reaches_the_screens_and_bad_commands_are_ignored():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/2") as ws2, client.websocket_connect("/ws/admin") as admin:
            assert ws2.receive_json()["view"] == "standby"
            admin.receive_json()

            admin.send_json({"type": "admin_command", "action": "xoa_het"})
            admin.send_text("khong phai json")
            admin.send_json({"type": "admin_command", "action": "blackout_on"})

            assert ws2.receive_json()["view"] == "blackout"
            snap = _recv_until(admin, lambda m: m["blackout"])
            assert snap["screens"][1]["connected"] is True


def test_screen_socket_still_rejects_non_numeric_ids():
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/khong-phai-so"):
                pass


def test_slice_route_is_404_until_slices_exist():
    with TestClient(app) as client:
        resp = client.get("/standby-video/5/0")
        assert resp.status_code == 404


def test_slice_route_serves_a_ready_slice(tmp_path):
    part = tmp_path / "slice_1.mp4"
    part.write_bytes(b"\x00" * 64)

    class ReadySlicer:
        def slice_path(self, wall_count, index):
            return part if (wall_count, index) == (3, 1) else None

        def cancel(self):
            pass

    with TestClient(app) as client:
        client.app.state.slicer = ReadySlicer()
        resp = client.get("/standby-video/3/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"
        assert client.get("/standby-video/3/2").status_code == 404
