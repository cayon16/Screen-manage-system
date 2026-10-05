"""Phần dùng chung cho các script kiểm tra thủ công trong thư mục này.

Không phải test tự động (pytest) — đây là các bài kiểm tra cần mở cửa sổ thật, chạm thật.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parent.parent

# Cửa sổ lệnh mặc định của Windows dùng cp1252 — in chữ có dấu sẽ làm script chết giữa bài.
for _luong in (sys.stdout, sys.stderr):
    if hasattr(_luong, "reconfigure"):
        _luong.reconfigure(encoding="utf-8", errors="replace")


def nap_duong_dan() -> None:
    """Cho phép `import desktop...` và `import app...` khi chạy script trực tiếp."""
    for path in (SYSTEM_DIR / "backend", SYSTEM_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


nap_duong_dan()

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QGuiApplication


class KetQua:
    """Ghi lại từng mục kiểm tra rồi in tổng kết."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool]] = []

    def kiem(self, ten: str, dat, chi_tiet="") -> None:
        dat = bool(dat)
        self.rows.append((ten, dat))
        print(("DAT   " if dat else "HONG  ") + ten + (f"  [{chi_tiet}]" if chi_tiet else ""), flush=True)

    def tong_ket(self) -> int:
        dat = sum(1 for _, ok in self.rows if ok)
        print(f"\n{dat}/{len(self.rows)} muc dat", flush=True)
        return 0 if dat == len(self.rows) else 1


class KichBan:
    """Chạy các bước TUẦN TỰ: bước sau chỉ hẹn giờ sau khi bước trước chạy xong.

    (Hẹn giờ tất cả cùng lúc sẽ bị dồn cục khi một bước chạy lâu — vd chụp ảnh màn hình.)
    """

    def __init__(self, ket_qua: KetQua) -> None:
        self.ket_qua = ket_qua
        self._buoc: list[tuple[int, callable]] = []

    def buoc(self, cho_ms: int, ham) -> None:
        self._buoc.append((cho_ms, ham))

    def chay(self, xong=None) -> None:
        def tiep(i: int) -> None:
            if i >= len(self._buoc):
                if xong:
                    xong()
                return
            cho_ms, ham = self._buoc[i]

            def lam():
                try:
                    ham()
                except Exception as exc:
                    self.ket_qua.kiem(f"buoc {i}", False, repr(exc))
                tiep(i + 1)

            QTimer.singleShot(cho_ms, lam)

        tiep(0)


# ---------- tìm phần tử trong cây QML ----------


def duyet(item):
    yield item
    for con in item.childItems():
        yield from duyet(con)


def tim(window, dieu_kien):
    """Phần tử QML đang hiện thoả điều kiện (None nếu không có)."""
    for item in duyet(window.contentItem()):
        try:
            if item.isVisible() and dieu_kien(item):
                return item
        except RuntimeError:
            continue
    return None


def tim_chu(window, chu: str):
    return tim(window, lambda i: i.property("text") == chu)


def tim_phim(window, nhan: str):
    nhan = "dấu cách" if nhan == " " else nhan
    return tim(window, lambda i: i.property("label") == nhan)


def tim_nut_gui(window):
    """Nút gửi (mũi tên) — nhận ra bằng đoạn đầu đường vẽ biểu tượng trong Icons.qml."""
    return tim(window, lambda i: "M4.5 12h15" in str(i.property("icon") or ""))


# ---------- toạ độ thật để chạm ----------


def toa_do_that(window, item, fx: float = 0.5, fy: float = 0.5) -> tuple[int, int]:
    """Điểm giữa (mặc định) của phần tử, tính bằng pixel vật lý của màn — máy chạm cần số này."""
    diem = item.mapToGlobal(QPointF(item.width() * fx, item.height() * fy))
    man = window.screen()
    khung = man.geometry()
    ti_le = man.devicePixelRatio()
    return (int(khung.x() + (diem.x() - khung.x()) * ti_le),
            int(khung.y() + (diem.y() - khung.y()) * ti_le))


def tam_cua_so(window) -> tuple[int, int]:
    return toa_do_that(window, window.contentItem())


def chup(window, duong_dan: Path) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    window.grabWindow().save(str(duong_dan))


def cho(giay: float) -> None:
    """Chờ nhưng vẫn cho giao diện vẽ."""
    het = time.time() + giay
    while time.time() < het:
        QGuiApplication.processEvents()
        time.sleep(0.02)


# ---------- máy chạm giả lập ----------


class MayCham:
    """1 đối tượng = 1 thiết bị cảm ứng ảo của Windows (mỗi tiến trình 1 thiết bị).

    Muốn giả lập 2 màn cảm ứng thì tạo 2 cái — đúng như 2 màn thật là 2 thiết bị riêng.
    """

    def __init__(self) -> None:
        self._proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).parent / "gia_lap_cham.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.san_sang = self._proc.stdout.readline().strip().startswith("SAN_SANG True")

    def _gui(self, lenh: str) -> str:
        self._proc.stdin.write(lenh + "\n")
        self._proc.stdin.flush()
        return self._proc.stdout.readline().strip()

    def cham(self, x: int, y: int, giu_ms: int | None = None) -> None:
        self._gui(f"cham {x} {y} {giu_ms}" if giu_ms else f"cham {x} {y} 60")

    def phim(self, to_hop: str) -> None:
        """Gửi phím thật, vd "ctrl+shift+q"."""
        self._gui(f"phim {to_hop}")

    def thiet_bi(self) -> str:
        return self._gui("thiet_bi")

    def dong(self) -> None:
        with contextlib.suppress(OSError):
            self._gui("thoat")


def cham_dong_thoi(may_a: MayCham, diem_a, may_b: MayCham, diem_b, giu_ms: int = 60) -> None:
    """Hai thiết bị chạm gần như cùng lúc (2 người dùng 2 màn)."""
    for may, diem in ((may_a, diem_a), (may_b, diem_b)):
        may._proc.stdin.write(f"cham {diem[0]} {diem[1]} {giu_ms}\n")
        may._proc.stdin.flush()
    for may in (may_a, may_b):
        may._proc.stdout.readline()
