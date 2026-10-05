from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.config import ALL_SCREENS


class LayoutError(ValueError):
    """Bo cuc man app Qt gui len khong hop le."""


@dataclass(frozen=True)
class ClusterLayout:
    """Nhung vai tro man nao dang co that, va moi man dung o vi tri nao trong day man hien thi.

    Vai tro (role) la so 1..5 theo dac ta: 1/3/5 chieu slide, 2 dieu khien, 4 chat.
    Vi tri tuong (wall_index) la thu tu TRAI -> PHAI cua man hien thi, dung de cat video cho.
    Hai thu nay khac nhau: vd 1 man cam ung + 2 man thuong xep trai->phai la [thuong, cam ung,
    thuong] thi vai tro la [1, 2, 3] nhung neu man cam ung nam ben trai cung thi vai tro la
    [2, 1, 3] — vi tri tuong van la 0, 1, 2.

    App Qt la noi DUY NHAT biet co bao nhieu man va man nao cam ung; backend chi nhan ket qua.
    """

    wall_index: dict[int, int] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "ClusterLayout":
        """Khi chua co app nao bao bo cuc: coi nhu du 5 man xep dung thu tu 1..5."""
        return cls({role: role - 1 for role in ALL_SCREENS})

    @classmethod
    def from_displays(cls, displays: Iterable[tuple[int, int]]) -> "ClusterLayout":
        """displays: cac cap (role, wall_index). Kiem tra chat vi bo cuc sai se lam lech hinh."""
        pairs = list(displays)
        if not pairs:
            raise LayoutError("Phai co it nhat 1 man hien thi")

        roles = [r for r, _ in pairs]
        bad = sorted({r for r in roles if r not in ALL_SCREENS})
        if bad:
            raise LayoutError(f"Vai tro khong ton tai: {bad}")
        if len(set(roles)) != len(roles):
            raise LayoutError(f"Vai tro bi trung: {sorted(roles)}")

        indices = sorted(i for _, i in pairs)
        if indices != list(range(len(pairs))):
            raise LayoutError(f"Vi tri tuong phai la 0..{len(pairs) - 1}, dang la {indices}")

        return cls(dict(pairs))

    @property
    def roles(self) -> tuple[int, ...]:
        """Cac vai tro dang co, xep theo so vai tro."""
        return tuple(sorted(self.wall_index))

    @property
    def wall_count(self) -> int:
        return len(self.wall_index)

    def is_active(self, role: int) -> bool:
        return role in self.wall_index

    def as_dict(self) -> dict:
        return {
            "wall_count": self.wall_count,
            "displays": [
                {"role": role, "wall_index": idx}
                for role, idx in sorted(self.wall_index.items(), key=lambda kv: kv[1])
            ],
        }
