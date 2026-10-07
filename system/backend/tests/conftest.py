import pytest

from app.db import ChatStore
from app.state.cluster_controller import ClusterController
from app.superdoc.base import ChatContext, SuperdocError, Turn


class RecordingSender:
    """Thay cho ConnectionManager that: giu lai moi message da gui de test kiem tra."""

    def __init__(self):
        self.messages: list[tuple[int, object]] = []

    async def __call__(self, screen_id, message):
        self.messages.append((screen_id, message))

    def to(self, screen_id: int, msg_type: str | None = None) -> list:
        return [
            m
            for sid, m in self.messages
            if sid == screen_id and (msg_type is None or m.type == msg_type)
        ]


class FakeProvider:
    """Provider dieu khien duoc: tra loi ngay lap tuc, hoac nem loi theo yeu cau cua test.
    Khong ngu, khong goi mang — test khong duoc phu thuoc thoi gian that hay internet."""

    name = "fake"

    def __init__(self, answer: str = "Đây là câu trả lời thử.", fail: bool = False):
        self.answer = answer
        self.fail = fail
        self.calls: list[list[Turn]] = []
        self.contexts: list[ChatContext] = []
        self.ended_sessions: list[str] = []
        self.end_reasons: list[str] = []

    async def reply(self, history, context=None):
        self.calls.append(list(history))
        self.contexts.append(context)
        if self.fail:
            raise SuperdocError("loi gia lap")
        return self.answer

    async def end_session(self, context, reason=""):
        self.ended_sessions.append(context.session_id)
        self.end_reasons.append(reason)

    async def aclose(self):
        return None


@pytest.fixture
def store(tmp_path) -> ChatStore:
    """Database rieng cho tung test — khong dung chung file pentasync.db that."""
    s = ChatStore(tmp_path / "test_pentasync.db")
    s._init_sync()
    return s


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def controller(sender, provider, store) -> ClusterController:
    return ClusterController(send=sender, provider=provider, store=store)
