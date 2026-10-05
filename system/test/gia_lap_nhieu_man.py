"""Giả lập nhiều màn trên 1 màn thật để chạy trọn luồng (máy dev chỉ có 1 màn).

    python test\\gia_lap_nhieu_man.py            6 màn: 1 quản lý + 5 hiển thị (2 cảm ứng)
    python test\\gia_lap_nhieu_man.py PTPTP      tự đặt: P = màn thường, T = màn cảm ứng, trái→phải
    python test\\gia_lap_nhieu_man.py PPTPTP --do-tai-nguyen   đo CPU/RAM khi các màn phát video chờ

Các "màn" giả nằm chồng lên nhau trên màn thật (không kiểm được căn chỉnh — việc đó đã có
`kiem_tra_cham.py` và log "Màn N khớp …"), nhưng kiểm được: gán vai trò, đánh thức, slide, chat,
màn đen, reset, bảng điều khiển. Ảnh từng bước lưu ở test\\anh\\nhieu_man\\.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from chung import KetQua, KichBan, chup

BO_CUC = next((a for a in sys.argv[1:] if not a.startswith("--")), "PPTPTP")
DO_TAI_NGUYEN = "--do-tai-nguyen" in sys.argv
ANH = Path(__file__).parent / "anh" / "nhieu_man"

os.environ["PENTASYNC_HOST_ACTIVITY"] = "0"

import desktop.main as dm
import desktop.window_manager as wm
from desktop.layout import Monitor
from desktop.monitors import ScreenEntry
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QMouseEvent

ket_qua = KetQua()
kich_ban = KichBan(ket_qua)
app_state: dict = {}


def man_gia(app):
    """Mỗi ký tự trong BO_CUC là 1 màn ảo 1920×1080 xếp cạnh nhau."""
    screen = app.primaryScreen()
    return [
        ScreenEntry(
            monitor=Monitor(key=f"\\\\.\\ẢO{i + 1}", x=i * 1920, y=0, width=1920, height=1080,
                            primary=(i == 0), touch=(ky_tu.upper() == "T")),
            screen=screen, scale_percent=150, handle=0)
        for i, ky_tu in enumerate(BO_CUC)
    ]


wm.read_screens = man_gia
wm.touch_devices = lambda: []


def man(vai_tro: int):
    return next(s for s in app_state["quan_ly"]._slots.values() if s.role == vai_tro)


def khung_nhin(vai_tro: int) -> str:
    return man(vai_tro).client.property("view")


def moi_khung_nhin() -> dict[int, str]:
    return {s.role: s.client.property("view") for s in sorted(app_state["quan_ly"]._slots.values(),
                                                              key=lambda s: s.role)}


def cham(vai_tro: int) -> None:
    """Chạm giả bằng sự kiện chuột gửi thẳng vào cửa sổ (đi qua đúng bộ lọc đánh thức của app)."""
    w = man(vai_tro).window
    diem = QPointF(30, 30)
    for loai, nut in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                      (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        QGuiApplication.sendEvent(w, QMouseEvent(loai, diem, w.mapToGlobal(diem),
                                                 Qt.MouseButton.LeftButton, nut,
                                                 Qt.KeyboardModifier.NoModifier))


def chup_tat_ca(ten: str) -> None:
    for slot in app_state["quan_ly"]._slots.values():
        chup(slot.window, ANH / f"{ten}_man{slot.role}.png")
    if app_state["quan_ly"]._management is not None:
        chup(app_state["quan_ly"]._management, ANH / f"{ten}_bang_dieu_khien.png")


def do_tai_nguyen(giay: int) -> dict:
    import psutil
    toi = psutil.Process(os.getpid())
    da_luu: dict[int, psutil.Process] = {}
    mau = []
    het = time.time() + giay
    lan_dau = True
    while time.time() < het:
        cay = [toi, *toi.children(recursive=True)]
        dwm = [p for p in psutil.process_iter(["name"]) if p.info["name"] == "dwm.exe"]
        cpu = ram = 0
        for p in cay + dwm:
            try:
                nho = da_luu.setdefault(p.pid, p)
                cpu += nho.cpu_percent(None)
                if p in cay:
                    ram += nho.memory_info().rss
            except psutil.Error:
                pass
        if not lan_dau:
            mau.append((cpu / psutil.cpu_count(), ram / 2**20))
        lan_dau = False
        moc = time.time() + 1
        while time.time() < moc:
            QGuiApplication.processEvents()
            time.sleep(0.02)
    return {"cpu_phan_tram_may": round(sum(m[0] for m in mau) / len(mau), 1),
            "ram_mb": round(sum(m[1] for m in mau) / len(mau))}


def dung_kich_ban() -> None:
    b = kich_ban.buoc
    k = ket_qua.kiem
    quan_ly = app_state["quan_ly"]
    co_quan_ly = len(BO_CUC) >= 6
    vai_tro_cham = [s.role for s in quan_ly._slots.values() if s.role in (2, 4)]

    b(5000, lambda: k(f"bo cuc '{BO_CUC}' -> vai tro {sorted(s.role for s in quan_ly._slots.values())}", True))
    b(0, lambda: k("co man quan ly khi >= 6 man", (quan_ly.property("managementMode") == "fullscreen")
                   == co_quan_ly, quan_ly.property("managementMode")))
    b(0, lambda: k("khoi dong: moi man o video cho", set(moi_khung_nhin().values()) == {"standby"},
                   moi_khung_nhin()))
    b(0, lambda: chup_tat_ca("01_video_cho"))

    if DO_TAI_NGUYEN:
        b(500, lambda: k("do tai nguyen", True, do_tai_nguyen(20)))
        b(500, lambda: QGuiApplication.instance().quit())
        kich_ban.chay()
        return

    if 2 in vai_tro_cham:
        b(300, lambda: cham(2))
        b(1500, lambda: k("cham man 2 -> menu + cac man khac thuc day", khung_nhin(2) == "menu",
                          moi_khung_nhin()))
        b(0, lambda: chup_tat_ca("02_danh_thuc"))
        b(300, lambda: man(2).client.touch("menu_option_info"))
        b(1500, lambda: k("chon 'Thong tin benh vien' -> bang 6 nut", khung_nhin(2) == "slide_control"))
        b(300, lambda: man(2).client.selectSlide("noi_quy"))
        b(1200, lambda: k("chon slide tu man 2", True, moi_khung_nhin()))
        b(0, lambda: chup_tat_ca("03_trinh_chieu"))
    if 4 in vai_tro_cham:
        b(300, lambda: cham(4))
        b(1500, lambda: k("cham man 4 -> vao chat", khung_nhin(4) == "chat", khung_nhin(4)))
        b(300, lambda: k("gui cau hoi", man(4).client.sendChat("Mấy giờ bệnh viện mở cửa?")))
        b(3000, lambda: k("AI tra loi", man(4).client.messages.rowCount() >= 2,
                          man(4).client.messages.rowCount()))
        b(0, lambda: chup_tat_ca("04_chat"))

    b(300, lambda: quan_ly._admin.selectSlide("gio_lam_viec"))
    b(1200, lambda: k("chon slide tu bang dieu khien", True))
    b(300, lambda: quan_ly._admin.command("blackout_on"))
    b(1500, lambda: k("tat han man hinh -> moi man den", set(moi_khung_nhin().values()) == {"blackout"},
                      moi_khung_nhin()))
    b(0, lambda: chup_tat_ca("05_man_den"))
    b(300, lambda: [cham(v) for v in vai_tro_cham])
    b(1500, lambda: k("man den bo qua cham", set(moi_khung_nhin().values()) == {"blackout"},
                      moi_khung_nhin()))
    b(300, lambda: quan_ly._admin.command("blackout_off"))
    b(1500, lambda: k("bat lai -> ve video cho", set(moi_khung_nhin().values()) == {"standby"},
                      moi_khung_nhin()))
    b(300, lambda: quan_ly.resetSystem())
    b(3500, lambda: k("reset he thong -> cua so duoc tao lai, ve video cho",
                      set(moi_khung_nhin().values()) == {"standby"}, moi_khung_nhin()))
    b(300, lambda: quan_ly.identify())
    b(900, lambda: chup_tat_ca("06_nhan_dien"))
    b(0, lambda: k("nhan dien man", quan_ly.property("identifying") is True))
    b(500, lambda: QGuiApplication.instance().quit())
    kich_ban.chay()


class QuanLyThu(wm.WindowManager):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        app_state["quan_ly"] = self
        self._guard.stop()  # màn giả chồng lên nhau → bỏ qua phần canh vị trí
        QTimer.singleShot(0, dung_kich_ban)

    def _check_placement(self, report):
        return


def main() -> int:
    dm.WindowManager = QuanLyThu
    dm.main()
    print(f"\nAnh luu o: {ANH}")
    return ket_qua.tong_ket()


if __name__ == "__main__":
    sys.exit(main())
