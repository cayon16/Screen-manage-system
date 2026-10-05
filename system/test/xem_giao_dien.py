"""Dựng từng màn giao diện với dữ liệu giả rồi chụp ảnh — kiểm giao diện mà không cần backend.

    python test\\xem_giao_dien.py            cửa sổ 1280×720, ảnh lưu ở test\\anh\\giao_dien\\
    python test\\xem_giao_dien.py 1920x1080  đổi kích thước cửa sổ

Chạy nhanh (khoảng 10 giây) và **báo lỗi QML ngay** — dùng mỗi khi sửa file trong desktop\\qml\\.
"""

from __future__ import annotations

import sys
from pathlib import Path

from chung import KetQua, cho, chup, duyet, tim_chu, tim_phim

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

from desktop.config import FONTS_DIR, QML_DIR
from desktop.screen_client import ScreenClient
from desktop.standby_sync import StandbySync
from desktop.window_manager import TelexBridge

ANH = Path(__file__).parent / "anh" / "giao_dien"
KICH_THUOC = sys.argv[1] if len(sys.argv) > 1 else "1280x720"
ROI, CAO = (int(x) for x in KICH_THUOC.split("x"))

loi_qml: list[str] = []
qInstallMessageHandler(lambda muc, ctx, tin: loi_qml.append(f"{tin} ({ctx.file}:{ctx.line})"))


class QuanLyGia(QObject):
    """Thay cho WindowManager thật — chỉ cung cấp dữ liệu cho giao diện."""

    doi = Signal()

    def __init__(self):
        super().__init__()
        self._telex = TelexBridge(self)
        self._nhan_dien = False

    def _man(self):
        return [{"role": r, "width": 1920, "height": 1080, "touch": r in (2, 4), "scale": 150,
                 "device": f"\\\\.\\DISPLAY{r}",
                 "gpu": "Intel UHD Graphics 770" if r == 5 else "NVIDIA GeForce RTX 4070 Ti SUPER"}
                for r in (1, 2, 3, 4, 5)]

    identifying = Property(bool, lambda self: self._nhan_dien, notify=doi)
    identifySeconds = Property(int, lambda self: 10, constant=True)
    displays = Property("QVariantList", _man, notify=doi)
    monitorCount = Property(int, lambda self: 6, notify=doi)
    unusedCount = Property(int, lambda self: 0, notify=doi)
    managementMode = Property(str, lambda self: "fullscreen", notify=doi)
    hospitalName = Property(str, lambda self: "Bệnh viện Đa khoa", constant=True)
    touchWarning = Property(str, lambda self: "", notify=doi)
    telex = Property(QObject, lambda self: self._telex, constant=True)

    @Slot()
    def toggleManagement(self): pass

    @Slot()
    def identify(self): pass

    @Slot()
    def quit(self): pass

    @Slot()
    def resetSystem(self): pass


class QuanTriGia(QObject):
    """Thay cho AdminClient — trả về 1 ảnh chụp trạng thái dựng sẵn."""

    anh_doi = Signal()
    ket_noi_doi = Signal()

    def __init__(self, anh):
        super().__init__()
        self._anh = anh

    connected = Property(bool, lambda self: True, notify=ket_noi_doi)
    snapshot = Property("QVariantMap", lambda self: self._anh, notify=anh_doi)

    @Slot(str)
    def command(self, hanh_dong): print("  (bang dieu khien goi lenh:", hanh_dong, ")")

    @Slot(str)
    def selectSlide(self, slide_id): print("  (bang dieu khien chon slide:", slide_id, ")")


SLIDE = {"id": "quy_trinh", "screen_id": 3, "kind": "text", "title": "Quy trình khám bệnh",
         "subtitle": "5 bước từ lúc đến đến lúc nhận thuốc", "accent": "#1e5aa8",
         "bullets": ["Lấy số thứ tự tại quầy tiếp đón — Tầng 1",
                     "Đăng ký khám, xuất trình thẻ BHYT (nếu có)",
                     "Khám tại phòng theo số được gọi",
                     "Làm xét nghiệm / chẩn đoán hình ảnh nếu bác sĩ chỉ định",
                     "Nhận kết quả, đóng viện phí và lãnh thuốc tại Tầng 1"]}
NUT_SLIDE = [
    {"slide_id": "a", "screen_id": 1, "title": "Giới thiệu bệnh viện", "current": True},
    {"slide_id": "b", "screen_id": 1, "title": "Giờ làm việc", "current": False},
    {"slide_id": "c", "screen_id": 3, "title": "Nội quy bệnh viện", "current": False},
    {"slide_id": "d", "screen_id": 3, "title": "Quy trình khám bệnh", "current": True},
    {"slide_id": "e", "screen_id": 5, "title": "Sơ đồ khuôn viên", "current": True},
    {"slide_id": "f", "screen_id": 5, "title": "Liên hệ & Hỗ trợ", "current": False},
]


def trang_thai(vai_tro, ten_state, khung_nhin, du_lieu):
    return {"type": "state_update", "screen_id": vai_tro, "state": ten_state, "view": khung_nhin,
            "data": du_lieu}


def main() -> int:
    ket_qua = KetQua()
    app = QGuiApplication(sys.argv)
    for phong in FONTS_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(phong))
    app.setFont(QFont("Be Vietnam Pro"))

    engine = QQmlEngine()
    engine.addImportPath(str(QML_DIR))

    def nap(ten):
        thanh_phan = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_DIR / ten)))
        if thanh_phan.isError():
            print("LOI QML", ten, [e.toString() for e in thanh_phan.errors()])
            sys.exit(1)
        return thanh_phan

    quan_ly = QuanLyGia()
    mau_man_hien_thi = nap("DisplayWindow.qml")
    mau_bang_dieu_khien = nap("ManagementWindow.qml")
    cua_so_mo = []

    def mo_man(vai_tro):
        client = ScreenClient(vai_tro, url="ws://127.0.0.1:1/khong-ket-noi")
        client._connected = True
        sync = StandbySync()
        w = mau_man_hien_thi.createWithInitialProperties(
            {"client": client, "sync": sync, "manager": quan_ly, "role": vai_tro}, engine.rootContext())
        w.setProperty("info", {"role": vai_tro, "role_name": "Màn thử", "width": 1920, "height": 1080,
                               "scale": 150, "touch": True, "device": "\\\\.\\DISPLAY9",
                               "gpu": "NVIDIA GeForce RTX 4070 Ti SUPER"})
        w.resize(ROI, CAO)
        w.show()
        cua_so_mo.append((w, client, sync))
        return w, client

    canh = [
        ("menu", 2, trang_thai(2, "MENU", "menu", {})),
        ("bang_chon_slide", 2, trang_thai(2, "SLIDE_CONTROL", "slide_control", {"buttons": NUT_SLIDE})),
        ("cham_de_chat", 4, trang_thai(4, "PROMPT_CHAT_BUTTON", "prompt_chat", {})),
        ("slide_chu", 3, trang_thai(3, "SLIDE_MEMBER", "slide", {"slide": SLIDE})),
        ("man_den", 1, trang_thai(1, "STANDBY", "blackout", {})),
        ("chat", 2, trang_thai(2, "CHAT", "chat", {"session_id": "s1", "waiting_for_ai": False,
                                                   "in_error": False})),
    ]
    for ten, vai_tro, tin in canh:
        w, client = mo_man(vai_tro)
        client.handle_message(tin)
        client.connectedChanged.emit()
        cho(0.4)
        chup(w, ANH / f"{ten}.png")
        ket_qua.kiem(f"dung duoc man '{ten}'", True)
        if ten != "chat":
            continue

        # Khung chat: thêm hội thoại, mở bàn phím, gõ thử, các hộp thoại
        client._model.append("user", "Bệnh viện mấy giờ mở cửa?")
        client._model.append("assistant", "Bệnh viện khám từ 07:00 đến 16:30 các ngày thứ 2 đến thứ 6, "
                                          "thứ 7 khám buổi sáng đến 12:00. Khoa Cấp cứu trực 24/7.")
        client.handle_message(trang_thai(2, "CHAT", "chat", {"session_id": "s1", "waiting_for_ai": True,
                                                            "in_error": False}))
        cho(0.4)
        chup(w, ANH / "chat_dang_cho.png")
        client.handle_message(trang_thai(2, "CHAT", "chat", {"session_id": "s1", "waiting_for_ai": False,
                                                            "in_error": False}))
        khung_chat = next(i for i in duyet(w.contentItem()) if i.property("keyboardOpen") is not None)
        khung_chat.setProperty("keyboardOpen", True)
        for ky_tu in "khoa caaps cuwus owr ddaau":
            khung_chat.setProperty("draft", quan_ly.telex.typeKey(khung_chat.property("draft"), ky_tu))
        cho(0.4)
        chup(w, ANH / "chat_ban_phim.png")
        ket_qua.kiem("go Telex tren ban phim ao", khung_chat.property("draft") == "khoa cấp cứu ở đâu",
                     khung_chat.property("draft"))
        ket_qua.kiem("ban phim co du phim chu", tim_phim(w, "q") is not None and tim_phim(w, " ") is not None)
        client.handle_message({"type": "confirm_prompt", "screen_id": 2, "kind": "tier1_warning",
                               "session_id": "s1", "message": "?", "timeout_sec": 30})
        cho(0.4)
        chup(w, ANH / "chat_hoi_con_o_day.png")
        ket_qua.kiem("hien hop 'con o day khong' thi an ban phim",
                     khung_chat.property("keyboardOpen") is False)
        client.handle_message(trang_thai(2, "CHAT_CONFIRM_SWITCH", "chat",
                                         {"session_id": "s1", "waiting_for_ai": False, "in_error": False}))
        cho(0.4)
        chup(w, ANH / "chat_xac_nhan_doi_che_do.png")
        ket_qua.kiem("hop xac nhan doi che do", tim_chu(w, "Đồng ý, kết thúc") is not None)
        client.handle_message(trang_thai(2, "CHAT", "chat", {"session_id": "s1", "waiting_for_ai": False,
                                                            "in_error": True}))
        client.handle_message({"type": "error", "screen_id": 2, "session_id": "s1", "code": "ai_unavailable",
                               "message": "Hiện chưa kết nối được tới Superdoc. Bạn thử lại sau ít phút."})
        cho(0.4)
        chup(w, ANH / "chat_loi_ai.png")

    # Lớp nhận diện màn
    quan_ly._nhan_dien = True
    quan_ly.doi.emit()
    cho(0.4)
    chup(cua_so_mo[0][0], ANH / "nhan_dien_man.png")
    ket_qua.kiem("dung duoc lop nhan dien man", True)
    quan_ly._nhan_dien = False
    quan_ly.doi.emit()

    # Bảng điều khiển
    import time
    gio = time.time()
    anh_trang_thai = {
        "type": "admin_snapshot", "blackout": False, "started_at": gio - 15120, "wall_count": 5,
        "screens": [
            {"role": 1, "active": True, "wall_index": 0, "connected": True, "state": "SLIDE_MEMBER",
             "view": "slide", "chat_open": False, "chat_started_at": None, "slide_title": "Giới thiệu bệnh viện"},
            {"role": 2, "active": True, "wall_index": 1, "connected": True, "state": "MENU", "view": "menu",
             "chat_open": False, "chat_started_at": None, "slide_title": None},
            {"role": 3, "active": True, "wall_index": 2, "connected": True, "state": "SLIDE_MEMBER",
             "view": "slide", "chat_open": False, "chat_started_at": None, "slide_title": "Quy trình khám bệnh"},
            {"role": 4, "active": True, "wall_index": 3, "connected": True, "state": "CHAT", "view": "chat",
             "chat_open": True, "chat_started_at": gio - 128, "slide_title": None},
            {"role": 5, "active": True, "wall_index": 4, "connected": False, "state": "STANDBY",
             "view": "standby", "chat_open": False, "chat_started_at": None, "slide_title": None},
        ],
        "slides": NUT_SLIDE,
        "stats": {"chats_today": 37, "avg_chat_seconds": 106, "ai_errors_today": 2},
    }
    bang = mau_bang_dieu_khien.createWithInitialProperties(
        {"admin": QuanTriGia(anh_trang_thai), "manager": quan_ly, "windowed": False}, engine.rootContext())
    bang.resize(ROI, CAO)
    bang.show()
    cho(0.5)
    chup(bang, ANH / "bang_dieu_khien.png")
    ket_qua.kiem("bang dieu khien: du 5 the man", tim_chu(bang, "Màn 5") is not None)
    ket_qua.kiem("bang dieu khien: co nut thoat", tim_chu(bang, "Thoát ứng dụng") is not None)
    bang.setProperty("confirmAction", "reset")
    cho(0.4)
    chup(bang, ANH / "bang_dieu_khien_xac_nhan_reset.png")
    ket_qua.kiem("hop xac nhan reset", tim_chu(bang, "Reset ngay") is not None)

    that_su_loi = [t for t in loi_qml if "Connection refused" not in t]
    ket_qua.kiem("khong co canh bao QML", not that_su_loi, "\n".join(that_su_loi[:3]))
    print(f"\nAnh luu o: {ANH}")
    return ket_qua.tong_ket()


if __name__ == "__main__":
    sys.exit(main())
