import asyncio

import pytest

from app.commands import AiChangedCommand, ChatMessageCommand, TouchCommand
from app.config import SUPERDOC_SYSTEM_PROMPT
from app.state.cluster_controller import ClusterController
from app.superdoc import registry
from app.superdoc.manager import AiManager
from app.superdoc.settings import AiSettings, InternalSettings

from tests.conftest import FakeProvider
from tests.test_chat_flow import _drain, _open_chat

INTERNAL = AiSettings(mode="internal", internal=InternalSettings(base_url="http://bridge.test"))


def _touch(screen_id: int, target: str) -> TouchCommand:
    return TouchCommand(screen_id=screen_id, target=target)


async def _ask(controller, screen_id: int, session_id: str, text: str) -> None:
    await controller._handle(ChatMessageCommand(screen_id=screen_id, session_id=session_id, text=text))
    await _drain(controller)


class _Admin:
    def __init__(self):
        self.snapshots = []

    async def __call__(self, message):
        self.snapshots.append(message)


# ---------- ngu canh va ly do dong phien toi dung provider ----------


async def test_the_provider_gets_the_session_screen_and_system_prompt(controller, provider):
    session_id = await _open_chat(controller, 4)
    await _ask(controller, 4, session_id, "Mấy giờ khám?")

    context = provider.contexts[-1]
    assert (context.session_id, context.screen_id) == (session_id, 4)
    assert context.system_prompt == SUPERDOC_SYSTEM_PROMPT


async def test_the_provider_is_told_why_the_chat_ended(controller, provider):
    session_id = await _open_chat(controller, 4)
    await controller._handle(_touch(4, "exit_chat"))
    assert provider.ended_sessions == [session_id]
    assert provider.end_reasons == ["user_exit"]


# ---------- doi AI giua cac phien chat ----------


@pytest.fixture
def two_ais(monkeypatch):
    """registry.build tra FakeProvider tra loi theo che do — khong chay mang that."""
    made = {}

    def fake_build(settings, env=None):
        made[settings.mode] = FakeProvider(answer=f"AI-{settings.mode}")
        return made[settings.mode]

    monkeypatch.setattr(registry, "build", fake_build)
    return made


async def test_an_open_chat_keeps_its_ai_while_the_next_chat_uses_the_new_one(store, sender, two_ais, tmp_path):
    ai = AiManager(tmp_path / "ai.json", {})
    await ai.start()
    controller = ClusterController(send=sender, ai=ai, store=store)

    first = await _open_chat(controller, 4)
    await ai.apply(INTERNAL, test_first=False)
    assert ai.snapshot()["pinned_sessions"] == 1

    await _ask(controller, 4, first, "Câu hỏi 1")
    assert sender.to(4, "chat_message_ack")[-1].text == "AI-demo"  # van AI cu

    await controller._handle(_touch(4, "exit_chat"))
    assert two_ais["demo"].end_reasons == ["user_exit"]
    assert ai.snapshot()["pinned_sessions"] == 0

    second = await _open_chat(controller, 4)
    await _ask(controller, 4, second, "Câu hỏi 2")
    assert sender.to(4, "chat_message_ack")[-1].text == "AI-internal"  # chat moi dung AI moi


async def test_closing_every_chat_releases_the_ai_it_held(store, sender, two_ais, tmp_path):
    ai = AiManager(tmp_path / "ai.json", {})
    await ai.start()
    controller = ClusterController(send=sender, ai=ai, store=store)
    await _open_chat(controller, 4)
    await ai.apply(INTERNAL, test_first=False)

    await controller._handle(_touch(4, "exit_chat"))
    await controller._handle(_touch(4, "exit_chat"))  # dong lan nua khong lam hong dem phien
    assert ai.snapshot()["pinned_sessions"] == 0


# ---------- tinh trang AI di ra bang dieu khien ----------


async def test_admin_snapshot_carries_the_ai_summary(controller):
    assert controller.admin_snapshot().ai == {
        "mode": "demo", "provider": "fake", "model": None, "state": "unknown", "last_error_code": None,
    }


async def test_a_failing_ai_shows_up_in_the_admin_snapshot(store, sender):
    admin = _Admin()
    provider = FakeProvider(fail=True)
    controller = ClusterController(send=sender, ai=None, provider=provider, store=store, send_admin=admin)
    session_id = await _open_chat(controller, 4)
    await _ask(controller, 4, session_id, "Chào")

    assert controller.admin_snapshot().ai["state"] == "degraded"
    assert controller.admin_snapshot().ai["last_error_code"] == "ai_unavailable"
    assert admin.snapshots[-1].ai["state"] == "degraded"


async def test_ai_changed_command_republishes_the_snapshot(store, sender):
    admin = _Admin()
    controller = ClusterController(send=sender, provider=FakeProvider(), store=store, send_admin=admin)
    await controller._handle(AiChangedCommand())
    assert len(admin.snapshots) == 1


async def test_a_slow_ai_counts_as_a_timeout_in_the_status(store, sender):
    class Slow(FakeProvider):
        async def reply(self, history, context=None):
            await asyncio.sleep(10)

    ai = AiManager.fixed(Slow(), timeout_sec=0.05)
    controller = ClusterController(send=sender, ai=ai, store=store)
    session_id = await _open_chat(controller, 4)
    await controller._handle(ChatMessageCommand(screen_id=4, session_id=session_id, text="Chào"))
    for _ in range(40):
        await _drain(controller)
        if sender.to(4, "error"):
            break
        await asyncio.sleep(0.02)

    assert sender.to(4, "error")[-1].code == "ai_timeout"
    assert ai.snapshot()["status"]["last_error"]["code"] == "timeout"
