"""Kiểm tra app bằng CHẠM THẬT của Windows (không cần màn cảm ứng).

    python test\\kiem_tra_cham.py motman    1 màn cảm ứng: đi hết luồng chạm + phím tắt + tự sửa lệch cửa sổ
    python test\\kiem_tra_cham.py chuagan   cảm ứng chưa gán màn: phải có cảnh báo, màn nhận vai trò 1
    python test\\kiem_tra_cham.py haiman    2 người dùng 2 màn cảm ứng CÙNG LÚC (2 thiết bị chạm)

Ảnh chụp lưu ở test\\anh\\. App chiếm toàn màn hình vài chục giây rồi tự thoát.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

from chung import (
    KetQua, KichBan, MayCham, cham_dong_thoi, chup, tam_cua_so, tim, tim_chu, tim_nut_gui,
    tim_phim, toa_do_that,
)

CHE_DO = sys.argv[1] if len(sys.argv) > 1 else "motman"
ANH = Path(__file__).parent / "anh"

# Thời gian chờ ngắn để không phải đứng đợi; tắt "thao tác máy chủ" để chạm giả không bị lẫn.
os.environ["PENTASYNC_HOST_ACTIVITY"] = "0"
os.environ["PENTASYNC_TIER1_WARNING_SEC"] = "6"
os.environ["PENTASYNC_TIER1_CLEANUP_SEC"] = "40"
os.environ["PENTASYNC_TIER2_CLUSTER_IDLE_SEC"] = "90"
os.environ.pop("PENTASYNC_PORT", None)

from desktop import run

# Chiếm sẵn cổng 8000 như một chương trình lạ → app phải tự chọn cổng khác.
# Phải làm TRƯỚC khi nạp cấu hình (app.config đọc số cổng ngay lúc nạp).
chan_cong = socket.socket()
try:
    chan_cong.bind(("127.0.0.1", 8000))
    chan_cong.listen()
except OSError:
    chan_cong = None
run._choose_port()

import desktop.main as dm
import desktop.monitors as mon
import desktop.window_manager as wm
from desktop import win32
from desktop.layout import Monitor
from desktop.monitors import ScreenEntry
from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QGuiApplication

ket_qua = KetQua()
kich_ban = KichBan(ket_qua)
app_state: dict = {}


def man(vai_tro: int):
    return next(s for s in app_state["quan_ly"]._slots.values() if s.role == vai_tro)


def cua_so(vai_tro: int):
    return man(vai_tro).window


def khung_nhin(vai_tro: int) -> str:
    return man(vai_tro).client.property("view")


def khung_chat(vai_tro: int):
    return tim(cua_so(vai_tro), lambda i: i.property("keyboardOpen") is not None)


# ---------- giả lập màn ----------

if CHE_DO == "motman":
    # Như đã chạy Tablet PC Settings: màn duy nhất được Windows gán là màn cảm ứng.
    def cam_ung_da_gan():
        return [mon._native_handle(QGuiApplication.instance().primaryScreen())]

    mon.touch_devices = cam_ung_da_gan
    wm.touch_devices = cam_ung_da_gan

if CHE_DO == "haiman":
    NUA = {}

    def hai_man_gia(app):
        m = app.primaryScreen()
        khung = m.geometry()
        ti_le = m.devicePixelRatio()
        rong, cao = round(khung.width() * ti_le), round(khung.height() * ti_le)
        ds = []
        for i in range(2):
            ten = f"\\\\.\\NUA{i}"
            NUA[ten] = QRect(khung.x() + i * khung.width() // 2, khung.y(), khung.width() // 2, khung.height())
            ds.append(ScreenEntry(
                monitor=Monitor(key=ten, x=i * rong // 2, y=0, width=rong // 2, height=cao,
                                primary=(i == 0), touch=True),
                screen=m, scale_percent=round(ti_le * 100), handle=0))
        return ds

    def dat_nua_man(window, screen, force=False):
        khoa = next((k for k, s in app_state["quan_ly"]._slots.items() if s.window is window), None)
        if khoa in NUA:
            window.setScreen(screen)
            window.setGeometry(NUA[khoa])
            window.show()

    wm.read_screens = hai_man_gia
    wm.touch_devices = lambda: []
    wm._place_fullscreen = dat_nua_man


# ---------- kịch bản ----------


def kich_ban_mot_man(may: MayCham) -> None:
    b = kich_ban.buoc
    k = ket_qua.kiem
    b(6000, lambda: k("man duy nhat nhan vai tro 2 (cam ung)", man(2).role == 2))
    b(0, lambda: k("khoi dong o video cho", khung_nhin(2) == "standby", khung_nhin(2)))
    b(0, lambda: k("khong canh bao cam ung khi da gan dung", app_state["quan_ly"]._touch_warning == "",
                   app_state["quan_ly"]._touch_warning))
    # Lần chạm đầu tiên ngay sau khi app vừa khởi động thỉnh thoảng bị thiết bị ảo bỏ qua →
    # chạm lại nếu chưa đổi trạng thái (chỉ là đặc tính của giả lập, màn cảm ứng thật không vậy).
    b(0, lambda: may.cham(*tam_cua_so(cua_so(2))))
    b(1200, lambda: khung_nhin(2) == "standby" and may.cham(*tam_cua_so(cua_so(2))))
    b(1500, lambda: k("cham video cho -> menu", khung_nhin(2) == "menu", khung_nhin(2)))
    b(0, lambda: chup(cua_so(2), ANH / "cham_01_menu.png"))
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), tim_chu(cua_so(2), "Thông tin bệnh viện"))))
    b(1500, lambda: k("cham 'Thong tin benh vien' -> bang chon slide", khung_nhin(2) == "slide_control",
                      khung_nhin(2)))
    # Giữ tay lâu 1,2 giây — người lớn tuổi hay bấm kiểu này
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), tim_chu(cua_so(2), "Chat với Superdoc")), giu_ms=1200))
    b(1800, lambda: k("giu nut lau 1,2 giay van an -> chat", khung_nhin(2) == "chat", khung_nhin(2)))
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), tim_chu(cua_so(2), "Chạm vào đây để nhập câu hỏi…"))))
    b(800, lambda: k("cham o nhap -> ban phim hien", khung_chat(2).property("keyboardOpen") is True))
    b(0, lambda: [may.cham(*toa_do_that(cua_so(2), tim_phim(cua_so(2), ky_tu))) for ky_tu in "giowf khams"])
    b(800, lambda: k("go Telex bang cham", khung_chat(2).property("draft") == "giờ khám",
                     khung_chat(2).property("draft")))
    b(0, lambda: may.cham(*toa_do_that(cua_so(2), tim_phim(cua_so(2), "Xoá"))))
    b(500, lambda: k("phim Xoa", khung_chat(2).property("draft") == "giờ khá", khung_chat(2).property("draft")))
    b(0, lambda: may.cham(*toa_do_that(cua_so(2), tim_phim(cua_so(2), "m"))))
    b(500, lambda: k("go tiep sau khi xoa", khung_chat(2).property("draft") == "giờ khám",
                     khung_chat(2).property("draft")))
    b(0, lambda: chup(cua_so(2), ANH / "cham_02_ban_phim.png"))
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), tim_nut_gui(cua_so(2)))))
    b(2500, lambda: k("gui cau hoi -> AI tra loi", man(2).client.messages.rowCount() >= 2,
                      man(2).client.messages.rowCount()))
    b(0, lambda: k("gui xong ban phim van mo", khung_chat(2).property("keyboardOpen") is True))
    b(0, lambda: chup(cua_so(2), ANH / "cham_03_tra_loi.png"))
    # Chạm vùng hội thoại (đang có tin nhắn → nằm trên danh sách cuộn được)
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), cua_so(2).contentItem(), 0.5, 0.25)))
    b(800, lambda: k("cham vung hoi thoai -> an ban phim", khung_chat(2).property("keyboardOpen") is False))
    b(9000, lambda: k("im lang -> hoi 'con o day khong'", man(2).client.property("tier1Visible") is True,
                      man(2).client.property("tier1Visible")))
    b(0, lambda: chup(cua_so(2), ANH / "cham_04_hoi_con_o_day.png"))
    b(300, lambda: may.cham(*tam_cua_so(cua_so(2))))
    b(1000, lambda: k("cham bat ky dau -> tat hop thoai", man(2).client.property("tier1Visible") is False))
    b(300, lambda: may.cham(*toa_do_that(cua_so(2), tim_chu(cua_so(2), "Kết thúc"))))
    b(1500, lambda: k("cham 'Ket thuc' -> ve menu", khung_nhin(2) == "menu", khung_nhin(2)))
    b(0, lambda: k("ket thuc -> lich su chat bi xoa", man(2).client.messages.rowCount() == 0))


def kich_ban_chua_gan(may: MayCham) -> None:
    b = kich_ban.buoc
    k = ket_qua.kiem
    b(6000, lambda: k("cam ung chua gan man -> vai tro 1 (trinh chieu)", man(1).role == 1))
    b(0, lambda: k("co canh bao cam ung", "chưa gắn" in app_state["quan_ly"]._touch_warning,
                   app_state["quan_ly"]._touch_warning))
    b(0, lambda: may.cham(*tam_cua_so(cua_so(1))))
    b(1200, lambda: may.cham(*tam_cua_so(cua_so(1))))
    b(1500, lambda: k("man trinh chieu khong nhan cham", khung_nhin(1) == "standby", khung_nhin(1)))


def kich_ban_hai_man(may2: MayCham, may4: MayCham) -> None:
    b = kich_ban.buoc
    k = ket_qua.kiem
    TRAI, PHAI = "gioowf mowr", "caaps cuwus"  # gõ song song, độ dài bằng nhau

    def go_song_song():
        for a, b_ in zip(TRAI, PHAI, strict=True):
            cham_dong_thoi(may2, toa_do_that(cua_so(2), tim_phim(cua_so(2), a)),
                           may4, toa_do_that(cua_so(4), tim_phim(cua_so(4), b_)))

    b(6000, lambda: k("2 man cam ung -> vai tro 2 va 4",
                      sorted(s.role for s in app_state["quan_ly"]._slots.values()) == [2, 4]))
    b(0, lambda: cham_dong_thoi(may2, tam_cua_so(cua_so(2)), may4, tam_cua_so(cua_so(4))))
    b(1200, lambda: khung_nhin(2) == "standby"
      and cham_dong_thoi(may2, tam_cua_so(cua_so(2)), may4, tam_cua_so(cua_so(4))))
    b(1500, lambda: k("cham dong thoi: man 2 -> menu", khung_nhin(2) == "menu", khung_nhin(2)))
    b(0, lambda: k("cham dong thoi: man 4 -> chat", khung_nhin(4) == "chat", khung_nhin(4)))
    b(300, lambda: may2.cham(*toa_do_that(cua_so(2), tim_chu(cua_so(2), "Chat với Superdoc"))))
    b(1500, lambda: k("man 2 vao chat", khung_nhin(2) == "chat", khung_nhin(2)))
    b(300, lambda: cham_dong_thoi(
        may2, toa_do_that(cua_so(2), tim_chu(cua_so(2), "Chạm vào đây để nhập câu hỏi…")),
        may4, toa_do_that(cua_so(4), tim_chu(cua_so(4), "Chạm vào đây để nhập câu hỏi…"))))
    b(800, lambda: k("ca 2 ban phim cung mo",
                     khung_chat(2).property("keyboardOpen") and khung_chat(4).property("keyboardOpen"),
                     (khung_chat(2).property("keyboardOpen"), khung_chat(4).property("keyboardOpen"))))
    b(300, go_song_song)
    b(800, lambda: k("go song song: man 2 dung chu", khung_chat(2).property("draft") == "giờ mở",
                     khung_chat(2).property("draft")))
    b(0, lambda: k("go song song: man 4 dung chu", khung_chat(4).property("draft") == "cấp cứu",
                   khung_chat(4).property("draft")))
    b(0, lambda: chup(cua_so(2), ANH / "haiman_trai.png"))
    b(0, lambda: chup(cua_so(4), ANH / "haiman_phai.png"))
    b(300, lambda: cham_dong_thoi(may2, toa_do_that(cua_so(2), tim_nut_gui(cua_so(2))),
                                  may4, toa_do_that(cua_so(4), tim_nut_gui(cua_so(4)))))
    b(3000, lambda: k("ca 2 cung gui -> ca 2 co tra loi",
                      man(2).client.messages.rowCount() == 2 and man(4).client.messages.rowCount() == 2,
                      (man(2).client.messages.rowCount(), man(4).client.messages.rowCount())))
    b(0, lambda: k("2 phien chat rieng biet",
                   man(2).client.property("sessionId") != man(4).client.property("sessionId")))
    b(0, lambda: may4.cham(*toa_do_that(cua_so(4), tim_chu(cua_so(4), "Kết thúc"))))
    b(1500, lambda: k("ket thuc man 4 khong anh huong man 2",
                      khung_nhin(4) == "prompt_chat" and khung_nhin(2) == "chat"
                      and man(2).client.messages.rowCount() == 2, (khung_nhin(4), khung_nhin(2))))


def kich_ban_phim_tat_va_lech(may: MayCham, vai_tro: int) -> None:
    b = kich_ban.buoc
    k = ket_qua.kiem
    quan_ly = app_state["quan_ly"]
    b(300, lambda: may.phim("ctrl+shift+i"))
    b(1000, lambda: k("Ctrl+Shift+I -> nhan dien man", quan_ly.property("identifying") is True))
    b(0, lambda: chup(cua_so(vai_tro), ANH / "cham_05_nhan_dien.png"))
    b(300, lambda: may.phim("ctrl+shift+m"))
    b(1500, lambda: k("Ctrl+Shift+M -> mo bang dieu khien", quan_ly.property("managementMode") == "window"))
    b(300, lambda: may.phim("ctrl+shift+m"))
    b(1000, lambda: k("Ctrl+Shift+M lan 2 -> dong bang", quan_ly.property("managementMode") == ""))

    def lam_lech():
        win32.force_rect(int(cua_so(vai_tro).winId()), (100, 100, 800, 600), False)
        app_state["lech"] = win32.window_rect(int(cua_so(vai_tro).winId()))

    b(11000, lam_lech)  # chờ lớp nhận diện tắt
    b(0, lambda: k("da lam lech cua so", app_state["lech"] == (100, 100, 800, 600), app_state["lech"]))
    b(11000, lambda: k("app tu sua cua so ve dung man", win32.rect_matches(
        win32.window_rect(int(cua_so(vai_tro).winId())),
        quan_ly._targets[next(iter(quan_ly._targets))].entry.rect),
        win32.window_rect(int(cua_so(vai_tro).winId()))))
    b(0, lambda: k("backend chay tren cong thay the", quan_ly._backend.is_ready,
                   os.environ.get("PENTASYNC_PORT")))


# ---------- chạy ----------

may_cham: list[MayCham] = []


class QuanLyThu(wm.WindowManager):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        app_state["quan_ly"] = self
        if CHE_DO == "haiman":
            self._guard.stop()  # 2 "màn" giả chồng lên 1 màn thật → không kiểm vị trí
        QTimer.singleShot(0, dung_kich_ban)

    def _check_placement(self, report):
        if CHE_DO != "haiman":
            super()._check_placement(report)


def dung_kich_ban() -> None:
    if CHE_DO == "haiman":
        kich_ban_hai_man(may_cham[0], may_cham[1])
    elif CHE_DO == "chuagan":
        kich_ban_chua_gan(may_cham[0])
        kich_ban_phim_tat_va_lech(may_cham[0], 1)
    else:
        kich_ban_mot_man(may_cham[0])
        kich_ban_phim_tat_va_lech(may_cham[0], 2)
    kich_ban.chay(xong=lambda: QTimer.singleShot(500, QGuiApplication.instance().quit))


def main() -> int:
    so_may = 2 if CHE_DO == "haiman" else 1
    for _ in range(so_may):
        may_cham.append(MayCham())
    if not all(m.san_sang for m in may_cham):
        print("Khong khoi tao duoc thiet bi cham ao")
        return 1
    dm.WindowManager = QuanLyThu
    dm.main()
    for may in may_cham:
        may.dong()
    if chan_cong:
        chan_cong.close()
    return ket_qua.tong_ket()


if __name__ == "__main__":
    sys.exit(main())
