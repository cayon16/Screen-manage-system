"""Kiểm bản đóng gói: chạy PentaSync.exe thật rồi thử các tình huống hay gặp ở máy khách.

    python test\\kiem_tra_exe.py                     dùng dist\\PentaSync
    python test\\kiem_tra_exe.py D:\\PentaSync        thư mục khác (vd bản vừa chép sang USB)

Kiểm: khởi động được 2 tiến trình, cửa sổ khớp màn, tự đổi cổng khi 8000 bị chiếm, backend bị
giết thì tự dựng lại và nhận lại bố cục, phím tắt thoát, không sót tiến trình, log không có lỗi lạ.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil
from chung import SYSTEM_DIR, KetQua, MayCham

THU_MUC = Path(sys.argv[1]) if len(sys.argv) > 1 else SYSTEM_DIR / "dist" / "PentaSync"
EXE = THU_MUC / "PentaSync.exe"
ket_qua = KetQua()


def cac_tien_trinh():
    ra = []
    for p in psutil.process_iter(["name", "cmdline"]):
        if p.info["name"] == "PentaSync.exe":
            ra.append(p)
    return ra


def cho_den_khi(dieu_kien, giay: float) -> bool:
    het = time.time() + giay
    while time.time() < het:
        if dieu_kien():
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    if not EXE.is_file():
        print(f"Khong thay {EXE} — chay 'python packaging\\build.py' truoc")
        return 1
    if cac_tien_trinh():
        print("PentaSync.exe dang chay — dong truoc da")
        return 1

    log_app = THU_MUC / "data" / "pentasync_app_log.txt"
    log_backend = THU_MUC / "data" / "pentasync_log.txt"
    da_co = log_app.stat().st_size if log_app.exists() else 0

    def log_moi() -> str:
        return log_app.read_bytes()[da_co:].decode("utf-8", "replace") if log_app.exists() else ""

    chan_cong = socket.socket()
    chan_cong.bind(("127.0.0.1", 8000))
    chan_cong.listen()

    subprocess.Popen([str(EXE)], cwd=str(THU_MUC),
                     env={**os.environ, "PENTASYNC_HOST_ACTIVITY": "0"})
    ket_qua.kiem("khoi dong: 2 tien trinh (app + backend)",
                 cho_den_khi(lambda: len(cac_tien_trinh()) == 2, 25), [p.pid for p in cac_tien_trinh()])
    ket_qua.kiem("cua so khop man (dong 'khớp' trong log)", cho_den_khi(lambda: "khớp" in log_moi(), 25),
                 next((d for d in log_moi().splitlines() if "khớp" in d), "")[-90:])

    backend = next((p for p in cac_tien_trinh() if "--backend" in (p.info["cmdline"] or [])), None)
    cong = int(backend.environ().get("PENTASYNC_PORT", "8000")) if backend else 8000
    ket_qua.kiem("cong 8000 bi chiem -> tu doi cong khac", cong != 8000, cong)
    ket_qua.kiem("backend tra loi /healthz",
                 urllib.request.urlopen(f"http://127.0.0.1:{cong}/healthz", timeout=5).status == 200)

    pid_backend = backend.pid
    backend.kill()
    ket_qua.kiem("giet backend -> app dung lai backend moi",
                 cho_den_khi(lambda: len(cac_tien_trinh()) == 2
                             and all(p.pid != pid_backend for p in cac_tien_trinh()), 25))
    ket_qua.kiem("backend moi san sang", cho_den_khi(lambda: log_moi().count("Backend sẵn sàng") >= 2, 25))
    ket_qua.kiem("bo cuc man duoc gui lai cho backend moi",
                 log_backend.read_text(encoding="utf-8", errors="replace").count("Bo cuc man moi") >= 2)

    may = MayCham()
    may.phim("ctrl+shift+i")
    time.sleep(1.5)
    may.phim("ctrl+shift+q")
    ket_qua.kiem("Ctrl+Shift+Q -> thoat, khong sot tien trinh",
                 cho_den_khi(lambda: not cac_tien_trinh(), 20), [p.pid for p in cac_tien_trinh()])
    may.dong()
    chan_cong.close()

    la = [d for d in log_moi().splitlines()
          if (" ERROR " in d or " CRITICAL " in d) and "Backend dừng bất thường" not in d]
    ket_qua.kiem("log khong co loi la", not la, la[:3])
    return ket_qua.tong_ket()


if __name__ == "__main__":
    sys.exit(main())
