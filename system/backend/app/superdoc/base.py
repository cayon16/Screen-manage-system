from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


@dataclass(frozen=True)
class ChatContext:
    """Thong tin 1 phien chat gui kem moi lan goi AI.

    screen_id = 0 la lan kiem tra ket noi (khong thuoc man nao). Chi chatbot noi bo (bridge) moi
    duoc nhan session_id va screen_id; AI cong khai chi nhan noi dung hoi thoai + system prompt.
    """

    session_id: str
    screen_id: int
    system_prompt: str


class SuperdocError(Exception):
    """Loi khi goi AI (mat mang, API tu choi, qua thoi gian cho...).

    Man hinh gap loi tu hien thong bao cuc bo va tu don dep — KHONG lan sang man khac
    ("loi cua man nao, man do tu chiu trach nhiem" trong dac ta).

    `code` chi dung cho trang thai/thong ke (khong hien cho nguoi dung): "http_401", "http_429",
    "http_529", "timeout", "network", "bad_response", "empty_reply", "filtered", "not_configured".
    """

    def __init__(self, message: str, code: str = "ai_unavailable"):
        super().__init__(message)
        self.code = code


class SuperdocProvider(Protocol):
    """Cong giao tiep duy nhat giua he thong va AI.

    Them nha cung cap moi = them 1 file implement dung giao dien nay roi khai bao trong
    registry.py — khong phai dong vao ClusterController hay ChatSession.
    """

    name: str
    model: str | None

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        """Tra ve cau tra loi cho luot cuoi cung trong history. Nem SuperdocError neu that bai."""
        ...

    async def end_session(self, context: ChatContext, reason: str) -> None:
        """Bao cho AI biet doan chat da ket thuc (descryption.txt muc 3: "API cần ... thông báo
        cho AI kết thúc đoạn chat nếu cần").

        Voi cac provider khong luu trang thai phia server (mock, Gemini, GPT, Claude) day la no-op.
        Chatbot noi bo co the giu phien phia no — khi do day la cho goi endpoint dong phien.

        Loi o day KHONG duoc lam hong viec don dep phien — ChatSession tu nuot va ghi log.
        """
        ...

    async def aclose(self) -> None:
        ...


def normalize_history(history: Sequence[Turn]) -> list[Turn]:
    """Dua lich su ve dang moi nha cung cap deu chap nhan: bo luot rong, bo luot assistant dung
    dau (cat bot lich su cu co the bat dau bang cau tra loi cua AI), gop cac luot lien tiep cung
    vai tro (AI loi -> nguoi dung hoi tiep -> 2 luot user lien nhau)."""
    out: list[Turn] = []
    for turn in history:
        text = turn.text.strip()
        if not text:
            continue
        if not out and turn.role != "user":
            continue
        if out and out[-1].role == turn.role:
            out[-1] = Turn(role=turn.role, text=f"{out[-1].text}\n{text}")
        else:
            out.append(Turn(role=turn.role, text=text))
    return out
