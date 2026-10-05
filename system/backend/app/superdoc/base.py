from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


class SuperdocError(Exception):
    """Loi khi goi AI (mat mang, API tu choi, qua thoi gian cho...).

    Man hinh gap loi tu hien thong bao cuc bo va tu don dep — KHONG lan sang man khac
    ("loi cua man nao, man do tu chiu trach nhiem" trong dac ta).
    """


class SuperdocProvider(Protocol):
    """Cong giao tiep duy nhat giua he thong va AI.

    Chatbot Superdoc that cua khach chua co tai lieu API. Khi co, chi can them 1 file provider
    moi implement dung giao dien nay va doi SUPERDOC_PROVIDER trong config — khong phai dong
    vao ClusterController hay ChatSession.
    """

    name: str

    async def reply(self, history: Sequence[Turn]) -> str:
        """Tra ve cau tra loi cho luot cuoi cung trong history. Nem SuperdocError neu that bai."""
        ...

    async def end_session(self, session_id: str) -> None:
        """Bao cho AI biet doan chat da ket thuc (descryption.txt muc 3: "API cần ... thông báo
        cho AI kết thúc đoạn chat nếu cần").

        Voi cac provider khong luu trang thai phia server (mock, Gemini generateContent) day la
        no-op. Chatbot Superdoc that co the la loai giu phien phia no — khi co tai lieu API, day
        chinh la cho goi endpoint dong phien, khong phai sua ChatSession hay ClusterController.

        Loi o day KHONG duoc lam hong viec don dep phien — ChatSession tu nuot va ghi log.
        """
        ...

    async def aclose(self) -> None:
        ...
