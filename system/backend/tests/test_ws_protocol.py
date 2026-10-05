import pytest
from starlette.testclient import TestClient

from app.main import app


def test_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_ws_connect_sends_initial_snapshot():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/1") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "state_update"
            assert snapshot["screen_id"] == 1
            assert snapshot["state"] == "STANDBY"
            assert snapshot["view"] == "standby"


def test_ws_invalid_screen_id_is_rejected():
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/99"):
                pass
            pytest.fail("Ky vong ket noi bi tu choi voi screen_id khong hop le")
        except Exception:
            pass  # server dong ket noi (close code 4004) — client raise khi handshake that bai


def test_ws_round_trip_touch_wakes_both_control_and_chat_screens():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/2") as ws2, client.websocket_connect("/ws/4") as ws4:
            ws2.receive_json()  # snapshot khoi tao
            ws4.receive_json()

            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})

            update2 = ws2.receive_json()
            assert update2["state"] == "MENU"

            update4 = ws4.receive_json()
            assert update4["state"] == "PROMPT_CHAT_BUTTON"


def test_ws_full_flow_menu_select_info_broadcasts_slide_to_passive_screens():
    with TestClient(app) as client:
        with (
            client.websocket_connect("/ws/1") as ws1,
            client.websocket_connect("/ws/2") as ws2,
            client.websocket_connect("/ws/3") as ws3,
        ):
            ws1.receive_json()
            ws2.receive_json()
            ws3.receive_json()

            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})
            assert ws2.receive_json()["state"] == "MENU"

            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "menu_option_info"})
            # Man 2 giu bang dieu khien 6 nut, chi man 1/3/5 thuc su trinh chieu.
            panel = ws2.receive_json()
            assert panel["state"] == "SLIDE_CONTROL"
            assert len(panel["data"]["buttons"]) == 6

            update1 = ws1.receive_json()
            assert update1["state"] == "SLIDE_MEMBER"
            assert update1["data"]["slide"]["screen_id"] == 1
            update3 = ws3.receive_json()
            assert update3["state"] == "SLIDE_MEMBER"


def test_standby_video_is_served_and_supports_range():
    # The <video> tua/phat muot duoc la nho HTTP Range; thieu no thi trinh duyet phai tai ca file
    # (hang tram MB) truoc khi hien duoc hinh dau tien.
    from app.config import STANDBY_VIDEO_PATH

    if not STANDBY_VIDEO_PATH.is_file():
        pytest.skip(f"Chua co video cho tai {STANDBY_VIDEO_PATH}")

    with TestClient(app) as client:
        resp = client.get("/standby-video", headers={"Range": "bytes=0-1023"})
        assert resp.status_code == 206
        assert len(resp.content) == 1024
        assert resp.headers["content-type"] == "video/mp4"


def test_standby_video_missing_file_explains_where_to_fix_it(monkeypatch, tmp_path):
    # Tren may khac ma duong dan sai thi ca 5 man se den thui — thong bao phai chi ro sua o dau.
    from app.routes import http_routes

    monkeypatch.setattr(http_routes, "STANDBY_VIDEO_PATH", tmp_path / "khong_co_that.mp4")

    with TestClient(app) as client:
        resp = client.get("/standby-video")
        assert resp.status_code == 404
        body = resp.json()
        assert "khong_co_that.mp4" in body["duong_dan_dang_tro_toi"]
        assert "STANDBY_VIDEO_REL_PATH" in body["sua_o"]


def test_media_route_serves_a_real_file():
    with TestClient(app) as client:
        resp = client.get("/media/README.txt")
        assert resp.status_code == 200
        assert "slides.json" in resp.text


def test_media_route_reports_a_missing_file_clearly():
    with TestClient(app) as client:
        resp = client.get("/media/khong_co_that.png")
        assert resp.status_code == 404
        assert "content_manifest/media" in resp.json()["error"]


@pytest.mark.parametrize("attack", ["..%2F..%2Fconfig.py", "....//config.py", "%2e%2e%2fapp%2fmain.py"])
def test_media_route_refuses_path_traversal(attack):
    # /media/{filename} doc file tu dia — khong duoc phep tro ra ngoai thu muc media.
    with TestClient(app) as client:
        resp = client.get(f"/media/{attack}")
        assert resp.status_code == 404


def test_ws_select_slide_updates_only_the_owning_screen():
    with TestClient(app) as client:
        with (
            client.websocket_connect("/ws/2") as ws2,
            client.websocket_connect("/ws/3") as ws3,
        ):
            ws2.receive_json()
            ws3.receive_json()

            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})
            ws2.receive_json()
            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "menu_option_info"})
            ws2.receive_json()
            assert ws3.receive_json()["data"]["slide"]["id"] == "noi_quy"

            ws2.send_json({"type": "select_slide", "screen_id": 2, "slide_id": "quy_trinh_kham"})

            assert ws3.receive_json()["data"]["slide"]["id"] == "quy_trinh_kham"
            # Man 2 cung duoc cap nhat de to sang dung nut vua bam.
            assert ws2.receive_json()["data"]["current"]["3"] == "quy_trinh_kham"


def test_ws_malformed_payload_does_not_crash_connection():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/2") as ws:
            ws.receive_json()  # snapshot khoi tao
            ws.send_json({"type": "not_a_real_type", "foo": "bar"})
            # Ket noi phai con song va van xu ly duoc message hop le tiep theo.
            ws.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})
            update = ws.receive_json()
            assert update["state"] == "MENU"


def test_ws_non_json_text_does_not_kill_connection():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/2") as ws:
            ws.receive_json()  # snapshot khoi tao
            ws.send_text("day khong phai JSON {{{")
            # Ket noi phai con song va van xu ly duoc message hop le tiep theo.
            ws.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})
            update = ws.receive_json()
            assert update["state"] == "MENU"


def test_ws_mismatched_screen_id_in_body_is_rejected():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/2") as ws2, client.websocket_connect("/ws/4") as ws4:
            ws2.receive_json()
            ws4.receive_json()

            # Ket noi la /ws/2 nhung body lai khai screen_id=4 — phai bi tu choi, khong duoc
            # phep dieu khien man 4 tu ket noi cua man 2.
            ws2.send_json({"type": "touch_event", "screen_id": 4, "target": "chat_button"})

            # Man 2 van hop le nen phai xu ly binh thuong tiep theo.
            ws2.send_json({"type": "touch_event", "screen_id": 2, "target": "generic_wake"})
            update2 = ws2.receive_json()
            assert update2["state"] == "MENU"
