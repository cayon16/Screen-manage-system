from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import CONTENT_MANIFEST_DIR, SLIDE_SCREENS
from app.logging_setup import get_logger

logger = get_logger()

MANIFEST_PATH = CONTENT_MANIFEST_DIR / "slides.json"
MEDIA_DIR = CONTENT_MANIFEST_DIR / "media"

# Dac ta cho phep man thu dong hien "1 doan video co truoc HOAC slide trinh chieu (da co)",
# nen 1 slide co the la chu go thang trong manifest, 1 tam anh, hoac 1 doan video.
KIND_TEXT = "text"
KIND_IMAGE = "image"
KIND_VIDEO = "video"
VALID_KINDS = (KIND_TEXT, KIND_IMAGE, KIND_VIDEO)


@dataclass(frozen=True)
class Slide:
    id: str
    screen_id: int
    kind: str
    title: str
    subtitle: str
    accent: str
    bullets: tuple[str, ...]
    src: str  # ten file trong content_manifest/media/ — rong voi slide chu

    def as_dict(self) -> dict:
        data = {
            "id": self.id,
            "screen_id": self.screen_id,
            "kind": self.kind,
            "title": self.title,
        }
        if self.kind == KIND_TEXT:
            data.update(
                {"subtitle": self.subtitle, "accent": self.accent, "bullets": list(self.bullets)}
            )
        else:
            # Frontend chi can duong dan HTTP, khong bao gio thay duong dan tren dia.
            data["src"] = f"/media/{self.src}"
        return data


class SlideBand:
    """Noi dung slide cua 3 man thu dong + trang thai "man nao dang chieu slide nao".

    Chi giu du lieu, khong tu gui gi ra ngoai — ClusterController quyet dinh khi nao broadcast.
    """

    def __init__(self, slides_by_screen: dict[int, tuple[Slide, ...]]):
        self._slides_by_screen = slides_by_screen
        self._current: dict[int, str] = {}
        self.reset()

    def reset(self) -> None:
        """Moi man ve slide dau tien cua no — trang thai mac dinh luc khoi dong va sau Reset he thong."""
        self._current = {
            screen_id: slides[0].id for screen_id, slides in self._slides_by_screen.items()
        }

    @classmethod
    def load(cls, path: Path = MANIFEST_PATH, media_dir: Path = MEDIA_DIR) -> "SlideBand":
        raw = json.loads(path.read_text(encoding="utf-8"))
        screens_raw = raw.get("screens", {})

        slides_by_screen: dict[int, tuple[Slide, ...]] = {}
        for screen_id in SLIDE_SCREENS:
            entries = screens_raw.get(str(screen_id))
            if not entries:
                raise ValueError(f"{path}: thieu noi dung slide cho man {screen_id}")
            slides_by_screen[screen_id] = tuple(
                cls._parse_slide(entry, screen_id, path, media_dir) for entry in entries
            )

        # slide_id phai duy nhat toan he thong vi bang dieu khien cua Man 2 chi gui ve 1 slide_id.
        all_ids = [s.id for slides in slides_by_screen.values() for s in slides]
        duplicates = {i for i in all_ids if all_ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"{path}: slide id bi trung: {sorted(duplicates)}")

        return cls(slides_by_screen)

    @staticmethod
    def _parse_slide(entry: dict, screen_id: int, path: Path, media_dir: Path) -> Slide:
        kind = entry.get("kind", KIND_TEXT)
        if kind not in VALID_KINDS:
            raise ValueError(
                f"{path}: slide {entry.get('id')!r} co kind={kind!r} khong hop le "
                f"(chi chap nhan {VALID_KINDS})"
            )

        src = entry.get("src", "")
        if kind != KIND_TEXT:
            if not src:
                raise ValueError(f"{path}: slide {entry.get('id')!r} kind={kind} nhung thieu 'src'")
            if "/" in src or "\\" in src:
                raise ValueError(
                    f"{path}: 'src' cua slide {entry.get('id')!r} phai la TEN FILE nam trong "
                    f"content_manifest/media/, khong phai duong dan ({src!r})"
                )
            if not (media_dir / src).is_file():
                # Canh bao chu khong nem loi: thieu 1 file noi dung khong duoc phep lam ca 5 man
                # hinh cua benh vien khong khoi dong duoc. Man do se hien thong bao ro rang.
                logger.warning(
                    "Slide %r tro toi file khong ton tai: %s", entry.get("id"), media_dir / src
                )

        return Slide(
            id=entry["id"],
            screen_id=screen_id,
            kind=kind,
            title=entry["title"],
            subtitle=entry.get("subtitle", ""),
            accent=entry.get("accent", "#1e5aa8"),
            bullets=tuple(entry.get("bullets", ())),
            src=src,
        )

    def buttons(self, screens: tuple[int, ...] | None = None) -> list[dict]:
        """Danh sach nut chon slide — mac dinh 3 man x 2 slide = 6 nut.

        screens: chi lay nut cua cac man nay (man khong ton tai thi nut cua no phai an di).
        Moi nut co co `current` de giao dien to sang dung slide dang chieu.
        """
        wanted = SLIDE_SCREENS if screens is None else tuple(s for s in SLIDE_SCREENS if s in screens)
        return [
            {
                "slide_id": slide.id,
                "screen_id": screen_id,
                "title": slide.title,
                "current": self._current.get(screen_id) == slide.id,
            }
            for screen_id in wanted
            for slide in self._slides_by_screen[screen_id]
        ]

    def screen_of(self, slide_id: str) -> int | None:
        for screen_id, slides in self._slides_by_screen.items():
            if any(s.id == slide_id for s in slides):
                return screen_id
        return None

    def select(self, slide_id: str) -> int | None:
        """Ghim slide_id len dung man phu trach no. Tra ve screen_id da doi, None neu id la."""
        screen_id = self.screen_of(slide_id)
        if screen_id is None:
            return None
        self._current[screen_id] = slide_id
        return screen_id

    def current_slide(self, screen_id: int) -> Slide | None:
        slides = self._slides_by_screen.get(screen_id)
        if not slides:
            return None
        current_id = self._current.get(screen_id)
        return next((s for s in slides if s.id == current_id), slides[0])
