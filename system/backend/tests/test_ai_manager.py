import asyncio
import json
from datetime import date

import pytest

from app.superdoc import registry
from app.superdoc.base import ChatContext, SuperdocError, Turn
from app.superdoc.manager import AiManager, AiTestFailed
from app.superdoc.registry import ProviderConfigError
from app.superdoc.settings import AiSettings, InternalSettings, PublicSettings, load_settings, save_settings

HOI = [Turn("user", "Khoa cấp cứu ở đâu?")]
CTX = ChatContext("phien-1", 4, "Bạn là Superdoc.")
INTERNAL = AiSettings(mode="internal", internal=InternalSettings(base_url="http://bridge.test"))


class Fake:
    def __init__(self, name="fake", fail=None):
        self.name = name
        self.model = "model-gia"
        self.fail = fail
        self.closed = False
        self.ended = []

    async def reply(self, history, context):
        if self.fail is not None:
            raise self.fail
        return "Trả lời thử"

    async def end_session(self, context, reason):
        self.ended.append((context.session_id, context.screen_id, reason))

    async def aclose(self):
        self.closed = True


class Builder:
    """Thay registry.build: dung provider gia thay vi goi mang that, va nho lai cac cai da dung."""

    def __init__(self):
        self.made: list[Fake] = []
        self.fail_next: SuperdocError | None = None

    def __call__(self, settings, env=None):
        provider = Fake(name=settings.mode, fail=self.fail_next)
        self.fail_next = None
        self.made.append(provider)
        return provider


@pytest.fixture
def builder(monkeypatch) -> Builder:
    b = Builder()
    monkeypatch.setattr(registry, "build", b)
    return b


async def _manager(tmp_path, env=None, on_change=None, settings: AiSettings | None = None) -> AiManager:
    path = tmp_path / "ai_settings.json"
    if settings is not None:
        save_settings(path, settings)
    manager = AiManager(path, env if env is not None else {}, on_change=on_change)
    await manager.start()
    return manager


# ---------- khoi dong ----------


async def test_starts_in_demo_mode_with_nothing_configured(tmp_path):
    manager = await _manager(tmp_path)
    snap = manager.snapshot()
    assert snap["active"]["mode"] == "demo"
    assert snap["status"]["state"] == "unknown"
    assert snap["problems"] == []
    assert manager.acquire().provider.name == "mock"


async def test_bad_configuration_does_not_fall_back_to_mock(tmp_path):
    # Man hinh benh vien ma tra loi bang du lieu gia con te hon la bao that "chua ket noi duoc".
    manager = await _manager(tmp_path, settings=AiSettings(mode="public", public=PublicSettings(provider="openai")))
    snap = manager.snapshot()
    assert snap["status"]["state"] == "down"
    assert snap["status"]["last_error"]["code"] == "not_configured"
    assert {p["field"] for p in snap["problems"]} == {"secrets.OPENAI_API_KEY", "public.model"}

    lease = manager.acquire()
    assert lease.provider.name == "unavailable"
    with pytest.raises(SuperdocError) as info:
        await lease.provider.reply(HOI, CTX)
    assert info.value.code == "not_configured"


# ---------- doi AI giua chung ----------


async def test_new_chats_use_the_new_ai_while_open_chats_keep_the_old_one(tmp_path, builder):
    manager = await _manager(tmp_path)
    old_lease = manager.acquire()
    old = builder.made[0]

    await manager.apply(INTERNAL, test_first=False)
    new_lease = manager.acquire()
    new = builder.made[-1]

    assert (old_lease.provider.inner, new_lease.provider.inner) == (old, new)
    assert manager.snapshot()["pinned_sessions"] == 1
    assert not old.closed  # chat dang do con dung no

    old_lease.release()
    await asyncio.sleep(0)
    assert old.closed
    assert manager.snapshot()["pinned_sessions"] == 0
    assert not new.closed


async def test_swapping_with_no_open_chats_closes_the_old_provider_at_once(tmp_path, builder):
    manager = await _manager(tmp_path)
    await manager.apply(INTERNAL, test_first=False)
    await asyncio.sleep(0)
    assert builder.made[0].closed


async def test_releasing_a_lease_twice_is_harmless(tmp_path, builder):
    manager = await _manager(tmp_path)
    first, second = manager.acquire(), manager.acquire()
    await manager.apply(INTERNAL, test_first=False)
    first.release()
    first.release()
    assert manager.snapshot()["pinned_sessions"] == 1  # second van giu AI cu
    second.release()
    assert manager.snapshot()["pinned_sessions"] == 0


async def test_a_retired_provider_does_not_pollute_the_status_of_the_new_one(tmp_path, builder):
    manager = await _manager(tmp_path)
    builder.made[0].fail = SuperdocError("hong", "http_500")
    old_lease = manager.acquire()
    await manager.apply(INTERNAL, test_first=False)

    with pytest.raises(SuperdocError):
        await old_lease.provider.reply(HOI, CTX)
    assert manager.snapshot()["status"]["consecutive_failures"] == 0
    assert manager.snapshot()["status"]["state"] == "unknown"


# ---------- thu ket noi truoc khi doi ----------


async def test_a_failed_probe_keeps_the_old_ai_and_closes_the_candidate(tmp_path, builder):
    manager = await _manager(tmp_path)
    builder.fail_next = SuperdocError("Chatbot nội bộ trả về HTTP 500", "http_500")

    with pytest.raises(AiTestFailed) as info:
        await manager.apply(INTERNAL)

    assert info.value.result["ok"] is False
    assert info.value.result["error"]["code"] == "http_500"
    assert manager.snapshot()["active"]["mode"] == "demo"
    assert manager.acquire().provider.inner is builder.made[0]
    assert builder.made[1].closed
    assert manager.snapshot()["status"]["last_test"]["ok"] is False
    assert not (tmp_path / "ai_settings.json").exists()  # cau hinh moi chua duoc luu


async def test_a_good_probe_applies_and_reports_the_result(tmp_path, builder):
    manager = await _manager(tmp_path)
    result = await manager.apply(INTERNAL)

    assert result["applied"] is True
    assert result["test"]["ok"] is True
    assert result["test"]["reply_preview"] == "Trả lời thử"
    assert result["active"]["mode"] == "internal"
    # Lan thu ket thuc phien thu de bot noi bo khong giu phien mo vo ich.
    assert builder.made[1].ended and builder.made[1].ended[0][1:] == (0, "connection_test")
    assert manager.snapshot()["status"]["last_test"]["ok"] is True


async def test_missing_configuration_is_refused_before_anything_is_built(tmp_path, builder):
    manager = await _manager(tmp_path)
    broken = AiSettings(mode="internal")  # chua nhap dia chi
    with pytest.raises(ProviderConfigError) as info:
        await manager.apply(broken)
    assert info.value.field == "internal.base_url"
    assert len(builder.made) == 1  # chi cai ban dau


async def test_apply_without_a_probe_skips_the_connection_test(tmp_path, builder):
    manager = await _manager(tmp_path)
    builder.fail_next = SuperdocError("hong", "http_500")
    result = await manager.apply(INTERNAL, test_first=False)  # ep doi du AI chua tra loi duoc
    assert result["test"] is None
    assert manager.snapshot()["active"]["mode"] == "internal"


# ---------- luu cau hinh ----------


async def test_applied_settings_survive_a_restart_and_never_contain_the_key(tmp_path, builder):
    env = {"GEMINI_API_KEY": "KHOA-BI-MAT-12345"}
    manager = await _manager(tmp_path, env=env)
    gemini = AiSettings(mode="public", public=PublicSettings(provider="gemini", model="gemini-x"))
    result = await manager.apply(gemini, test_first=False)
    assert result["saved"] is True

    text = (tmp_path / "ai_settings.json").read_text(encoding="utf-8")
    assert "KHOA-BI-MAT" not in text
    assert load_settings(tmp_path / "ai_settings.json", {}) == gemini


async def test_set_mode_keeps_the_rest_of_the_configuration(tmp_path, builder):
    manager = await _manager(tmp_path, settings=INTERNAL)
    await manager.set_mode("demo", test_first=False)
    snap = manager.snapshot()
    assert snap["active"]["mode"] == "demo"
    assert snap["settings"]["internal"]["base_url"] == "http://bridge.test"
    with pytest.raises(ValueError):
        await manager.set_mode("khong-co")


# ---------- theo doi tinh trang ----------


async def test_state_goes_ok_then_degraded_then_down_and_recovers(tmp_path, builder):
    manager = await _manager(tmp_path)
    provider = builder.made[0]
    lease = manager.acquire()
    state = lambda: manager.snapshot()["status"]["state"]  # noqa: E731

    await lease.provider.reply(HOI, CTX)
    assert state() == "ok"

    provider.fail = SuperdocError("hong", "http_500")
    for expected in ("degraded", "degraded", "down"):
        with pytest.raises(SuperdocError):
            await lease.provider.reply(HOI, CTX)
        assert state() == expected

    provider.fail = None
    await lease.provider.reply(HOI, CTX)
    status = manager.snapshot()["status"]
    assert (status["state"], status["consecutive_failures"]) == ("ok", 0)
    assert status["last_error"]["code"] == "http_500"  # van nho loi gan nhat
    assert status["calls_today"] == 5
    assert status["errors_today"] == 3


async def test_daily_counters_reset_after_midnight(tmp_path, builder):
    manager = await _manager(tmp_path)
    lease = manager.acquire()
    await lease.provider.reply(HOI, CTX)
    manager._status.day = date(2000, 1, 1)
    assert manager.snapshot()["status"]["calls_today"] == 0


async def test_a_timeout_reported_by_the_chat_session_counts_as_an_error(tmp_path, builder):
    manager = await _manager(tmp_path)
    manager.acquire().note_timeout()
    status = manager.snapshot()["status"]
    assert (status["state"], status["last_error"]["code"]) == ("degraded", "timeout")


async def test_the_panel_is_told_only_when_the_visible_state_changes(tmp_path, builder):
    calls = []

    async def on_change():
        calls.append(1)

    manager = await _manager(tmp_path, on_change=on_change)
    lease = manager.acquire()
    await lease.provider.reply(HOI, CTX)  # unknown -> ok
    await lease.provider.reply(HOI, CTX)  # van ok: khong bao lai
    assert len(calls) == 1

    builder.made[0].fail = SuperdocError("hong", "http_500")
    with pytest.raises(SuperdocError):
        await lease.provider.reply(HOI, CTX)  # ok -> degraded
    assert len(calls) == 2

    await manager.apply(INTERNAL, test_first=False)
    assert len(calls) == 3


async def test_a_failing_panel_callback_never_breaks_the_chat(tmp_path, builder):
    async def boom():
        raise RuntimeError("bang dieu khien hong")

    manager = await _manager(tmp_path, on_change=boom)
    assert await manager.acquire().provider.reply(HOI, CTX) == "Trả lời thử"


# ---------- thu ket noi thu cong ----------


async def test_manual_test_probes_the_running_ai_without_counting_it(tmp_path, builder):
    manager = await _manager(tmp_path)
    result = await manager.test()
    assert result["ok"] is True
    assert result["provider"] == "demo"
    status = manager.snapshot()["status"]
    assert status["calls_today"] == 0
    assert status["last_test"]["ok"] is True


async def test_manual_test_of_a_candidate_configuration_closes_it_afterwards(tmp_path, builder):
    manager = await _manager(tmp_path)
    result = await manager.test(INTERNAL)
    assert result["ok"] is True
    assert builder.made[1].closed
    assert manager.snapshot()["active"]["mode"] == "demo"  # chi thu, khong doi


async def test_manual_test_reports_failure_instead_of_raising(tmp_path, builder):
    manager = await _manager(tmp_path)
    builder.fail_next = SuperdocError("khong ket noi duoc", "network")
    result = await manager.test(INTERNAL)
    assert result["ok"] is False
    assert result["error"]["code"] == "network"


async def test_a_probe_that_takes_too_long_is_a_timeout(tmp_path, builder):
    manager = await _manager(tmp_path)

    class Slow(Fake):
        async def reply(self, history, context):
            await asyncio.sleep(10)

    manager._active.inner = Slow()
    manager._settings = manager._settings.model_copy(update={"timeout_sec": 0.05})
    result = await manager.test()
    assert (result["ok"], result["error"]["code"]) == (False, "timeout")


# ---------- an toan ----------


async def test_snapshot_reports_which_secrets_exist_but_never_their_values(tmp_path):
    env = {"GEMINI_API_KEY": "KHOA-BI-MAT-12345", "SUPERDOC_INTERNAL_TOKEN": "TOKEN-BI-MAT-67890"}
    manager = await _manager(tmp_path, env=env)
    snap = manager.snapshot()
    assert snap["secrets"] == {
        "GEMINI_API_KEY": True, "OPENAI_API_KEY": False, "ANTHROPIC_API_KEY": False, "SUPERDOC_INTERNAL_TOKEN": True,
    }
    dumped = json.dumps(snap, ensure_ascii=False)
    assert "BI-MAT" not in dumped
    assert "KHOA" not in dumped and "TOKEN-" not in dumped
    assert {c["provider"] for c in snap["catalog"]} >= {"gemini", "openai", "anthropic", "bridge"}


async def test_brief_is_a_small_summary_for_the_panel(tmp_path, builder):
    manager = await _manager(tmp_path)
    assert manager.brief() == {"mode": "demo", "provider": "mock", "model": None,
                               "state": "unknown", "last_error_code": None}


# ---------- che do co dinh (test) va dong ----------


async def test_fixed_manager_serves_one_provider_and_refuses_changes():
    provider = Fake(name="fake")
    manager = AiManager.fixed(provider, system_prompt="Prompt thử", timeout_sec=7)
    await manager.start()
    lease = manager.acquire()
    assert (lease.provider.inner, lease.system_prompt, lease.timeout_sec) == (provider, "Prompt thử", 7)
    assert manager.brief()["provider"] == "fake"
    with pytest.raises(RuntimeError):
        await manager.apply(INTERNAL)
    assert await manager.test()


async def test_aclose_closes_every_provider_it_still_holds(tmp_path, builder):
    manager = await _manager(tmp_path)
    manager.acquire()  # giu AI cu mo
    await manager.apply(INTERNAL, test_first=False)
    await manager.aclose()
    assert all(p.closed for p in builder.made)
