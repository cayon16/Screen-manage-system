import json

import pytest
from starlette.testclient import TestClient

from app import main as main_module
from app.main import app
from app.routes.ai_routes import require_local
from app.state.video_slicer import VideoSlicer
from app.superdoc import registry
from app.superdoc.base import SuperdocError

from tests.conftest import FakeProvider

INTERNAL = {"mode": "internal", "internal": {"protocol": "bridge", "base_url": "http://bridge.test"}}


class _Builder:
    """Thay registry.build: provider gia, khong cham mang. fail_next lam lan dung ke tiep hong."""

    def __init__(self):
        self.fail_next: SuperdocError | None = None

    def __call__(self, settings, env=None):
        provider = FakeProvider(answer=f"AI-{settings.mode}")
        if self.fail_next is not None:
            provider.fail = True
            self.fail_next = None
        return provider


@pytest.fixture(autouse=True)
def isolated_app(monkeypatch, tmp_path):
    # Khong duoc dung/ghi file cau hinh, cache video hay bien moi truong that cua may dang chay test.
    monkeypatch.setattr(main_module, "HOST_ACTIVITY_ENABLED", False)
    monkeypatch.setattr(VideoSlicer, "ensure", lambda self, n: None)
    monkeypatch.setattr(main_module, "STANDBY_SLICE_CACHE_DIR", tmp_path / "slices")
    monkeypatch.setattr(main_module, "AI_SETTINGS_PATH", tmp_path / "ai_settings.json")
    for name in ("SUPERDOC_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                 "SUPERDOC_INTERNAL_TOKEN", "SUPERDOC_INTERNAL_URL"):
        monkeypatch.delenv(name, raising=False)
    builder = _Builder()
    monkeypatch.setattr(registry, "build", builder)
    yield builder
    app.dependency_overrides.clear()


@pytest.fixture
def local():
    """TestClient co host la "testclient" nen phai coi nhu goi tu chinh may chay app."""
    app.dependency_overrides[require_local] = lambda: None


def _recv_until(ws, predicate, limit: int = 12) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("Khong nhan duoc message mong doi")


# ---------- chi goi duoc tu chinh may nay ----------


def test_every_route_refuses_callers_that_are_not_the_local_machine():
    with TestClient(app) as client:  # host cua TestClient la "testclient", khong phai 127.0.0.1
        responses = [
            client.get("/api/ai"),
            client.put("/api/ai/settings", json={}),
            client.post("/api/ai/mode", json={}),
            client.post("/api/ai/test"),
        ]
        for response in responses:
            assert response.status_code == 403, response.request.url
            assert "chính máy" in response.json()["error"]


# ---------- doc ----------


def test_get_returns_the_active_ai_without_any_secret_value(local, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "KHOA-BI-MAT-12345")
    with TestClient(app) as client:
        response = client.get("/api/ai")
    assert response.status_code == 200
    body = response.json()
    assert body["active"]["mode"] == "demo"
    assert body["secrets"]["GEMINI_API_KEY"] is True
    assert body["secrets"]["OPENAI_API_KEY"] is False
    assert {"settings", "status", "problems", "pinned_sessions", "catalog"} <= body.keys()
    assert "KHOA-BI-MAT" not in response.text


# ---------- doi cau hinh ----------


def test_put_settings_applies_after_a_successful_probe_and_saves_the_file(local, tmp_path):
    with TestClient(app) as client:
        response = client.put("/api/ai/settings", json=INTERNAL)
        assert response.status_code == 200
        body = response.json()
        assert body["applied"] is True
        assert body["test"]["ok"] is True
        assert body["active"] == {"mode": "internal", "provider": "bridge", "model": None,
                                  "base_url": "http://bridge.test"}
        assert client.get("/api/ai").json()["active"]["mode"] == "internal"
    saved = json.loads((tmp_path / "ai_settings.json").read_text(encoding="utf-8"))
    assert saved["mode"] == "internal"
    assert saved["internal"]["base_url"] == "http://bridge.test"


def test_put_settings_with_missing_configuration_says_which_field(local):
    with TestClient(app) as client:
        response = client.put("/api/ai/settings", json={"mode": "public", "public": {"provider": "openai"}})
        assert response.status_code == 400
        assert response.json()["field"] == "secrets.OPENAI_API_KEY"
        assert "OPENAI_API_KEY" in response.json()["error"]
        assert client.get("/api/ai").json()["active"]["mode"] == "demo"


def test_put_settings_rejects_malformed_bodies_and_stray_fields(local):
    with TestClient(app) as client:
        assert client.put("/api/ai/settings", json={"mode": "bat-ky"}).status_code == 422
        assert client.put("/api/ai/settings", json="sai").status_code == 422
        # Mot truong "api_key" khong duoc phep lot vao cau hinh.
        assert client.put("/api/ai/settings", json={**INTERNAL, "api_key": "khoa-gia"}).status_code == 422


def test_a_failed_probe_returns_424_and_keeps_the_old_ai_unless_forced(local, isolated_app):
    with TestClient(app) as client:
        isolated_app.fail_next = SuperdocError("hong")
        response = client.put("/api/ai/settings", json=INTERNAL)
        assert response.status_code == 424
        assert response.json()["test"]["ok"] is False
        assert "chưa đổi" in response.json()["error"]
        assert client.get("/api/ai").json()["active"]["mode"] == "demo"

        isolated_app.fail_next = SuperdocError("hong")
        forced = client.put("/api/ai/settings?test=false", json=INTERNAL)
        assert forced.status_code == 200
        assert forced.json()["test"] is None
        assert client.get("/api/ai").json()["active"]["mode"] == "internal"


def test_post_mode_switches_mode_and_keeps_the_rest(local):
    with TestClient(app) as client:
        client.put("/api/ai/settings", json=INTERNAL)
        response = client.post("/api/ai/mode", json={"mode": "demo"})
        assert response.status_code == 200
        assert response.json()["active"]["mode"] == "demo"
        # Cau hinh noi bo van con de bat lai bang 1 lenh.
        again = client.post("/api/ai/mode", json={"mode": "internal"})
        assert again.status_code == 200
        assert again.json()["active"]["base_url"] == "http://bridge.test"


def test_post_mode_refuses_a_mode_that_is_not_configured_and_bad_values(local):
    with TestClient(app) as client:
        response = client.post("/api/ai/mode", json={"mode": "public"})
        assert response.status_code == 400
        assert response.json()["field"] == "secrets.GEMINI_API_KEY"
        assert client.post("/api/ai/mode", json={"mode": "bat-ky"}).status_code == 422
        assert client.post("/api/ai/mode", json={}).status_code == 422


# ---------- thu ket noi ----------


def test_post_test_without_a_body_probes_the_running_ai(local):
    with TestClient(app) as client:
        response = client.post("/api/ai/test")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert client.get("/api/ai").json()["status"]["last_test"]["ok"] is True


def test_post_test_with_a_candidate_does_not_change_anything(local):
    with TestClient(app) as client:
        response = client.post("/api/ai/test", json=INTERNAL)
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert client.get("/api/ai").json()["active"]["mode"] == "demo"


def test_post_test_reports_failure_as_200_but_missing_configuration_as_400(local, isolated_app):
    with TestClient(app) as client:
        isolated_app.fail_next = SuperdocError("hong")
        failed = client.post("/api/ai/test", json=INTERNAL)
        assert failed.status_code == 200
        assert failed.json()["ok"] is False

        incomplete = client.post("/api/ai/test", json={"mode": "internal"})
        assert incomplete.status_code == 400
        assert incomplete.json()["field"] == "internal.base_url"


# ---------- bang dieu khien ----------


def test_admin_socket_shows_the_ai_and_hears_about_changes(local):
    with TestClient(app) as client, client.websocket_connect("/ws/admin") as admin:
        first = admin.receive_json()
        assert first["ai"]["mode"] == "demo"

        client.put("/api/ai/settings", json=INTERNAL)
        updated = _recv_until(admin, lambda m: m["ai"]["mode"] == "internal")
        assert updated["ai"]["provider"] == "bridge"
