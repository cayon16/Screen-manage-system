"""Launcher cho PentaSync: khoi dong backend, do 5 monitor vat ly, mo 5 cua so
Edge kiosk dung vi tri tren tung man, giam sat & don dep khi dung.

Chay thu (AN TOAN, khong mo gi ca — nen chay truoc it nhat 1 lan tren may that):
    python launcher.py --dry-run

Chay that (khoi dong backend + mo 5 cua so):
    python launcher.py

Neu thu tu man hinh bi sai (vd man ngoai cung trai lai duoc gan screen_id=3 thay vi 1),
doi chieu dong log "Vi tri #N" voi vi tri vat ly that roi dien MONITOR_INDEX_OVERRIDE
o duoi, KHONG sua code o noi khac.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from screeninfo import get_monitors

LAUNCHER_DIR = Path(__file__).resolve().parent
BACKEND_DIR = LAUNCHER_DIR.parent / "backend"

HOST = "127.0.0.1"
PORT = 8000
HEALTHZ_URL = f"http://{HOST}:{PORT}/healthz"
BACKEND_START_TIMEOUT_SEC = 15

EDGE_CANDIDATE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
]

# Neu thu tu man hinh do screeninfo phat hien (sap xep trai->phai theo toa do x) KHONG
# khop thu tu vat ly that, doi chieu dong log "Vi tri #N" voi thuc te roi dien override
# tai day. Vi du {0: 2} nghia la "man o vi tri sort-index 0" duoc gan screen_id=2 thay vi 1.
MONITOR_INDEX_OVERRIDE: dict[int, int] = {}

LOG_FILE = BACKEND_DIR / "launcher_log.txt"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def acquire_single_instance_lock():
    """Tra ve handle mutex — PHAI giu bien tham chieu song suot vong doi tien trinh
    (goi la _mutex = acquire_single_instance_lock() trong main(), khong duoc bo qua)."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\PentaSyncLauncherSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log("[CRITICAL] Launcher da chay roi (mutex dang giu boi tien trinh khac). Thoat.")
        sys.exit(1)
    return mutex


def find_edge() -> str:
    for path in EDGE_CANDIDATE_PATHS:
        if Path(path).is_file():
            log(f"Tim thay Edge tai: {path}")
            return path
    log(
        f"[CRITICAL] Khong tim thay Edge trong: {EDGE_CANDIDATE_PATHS}. "
        f"Sua EDGE_CANDIDATE_PATHS trong launcher.py neu Edge cai o duong dan khac."
    )
    sys.exit(1)


def detect_monitors_left_to_right():
    monitors = sorted(get_monitors(), key=lambda m: m.x)
    log(f"Phat hien {len(monitors)} man hinh (sap xep trai -> phai theo toa do x):")
    for i, m in enumerate(monitors):
        assigned = MONITOR_INDEX_OVERRIDE.get(i, i + 1)
        log(
            f"  Vi tri #{i}: x={m.x} y={m.y} w={m.width} h={m.height} "
            f"name={m.name!r} -> se gan screen_id={assigned}"
        )
    if len(monitors) != 5:
        log(
            f"[WARNING] Ky vong 5 man hinh nhung phat hien {len(monitors)}. "
            f"Kiem tra lai ket noi man hinh vat ly truoc khi chay that."
        )

    validate_screen_id_assignment(monitors)
    warn_if_monitor_widths_differ(monitors)
    return monitors


def validate_screen_id_assignment(monitors) -> None:
    """MONITOR_INDEX_OVERRIDE dien tay rat de sai. Neu 2 vi tri cung tro ve 1 screen_id thi
    2 cua so Edge cung mo /screen/N: backend chi giu duoc 1 ket noi WebSocket cho moi man, cua
    so con lai thanh "xac song" hien noi dung cu va khong bao gio cap nhat nua. Loi nay im lang
    tuyet doi luc chay — phai chan ngay tu buoc dry-run."""
    assigned = [MONITOR_INDEX_OVERRIDE.get(i, i + 1) for i in range(len(monitors[:5]))]

    duplicates = sorted({a for a in assigned if assigned.count(a) > 1})
    if duplicates:
        log(
            f"[CRITICAL] MONITOR_INDEX_OVERRIDE sai: screen_id {duplicates} bi gan cho nhieu vi tri "
            f"({assigned}). Moi man phai co dung 1 screen_id rieng. Sua lai roi chay lai --dry-run."
        )
        sys.exit(1)

    out_of_range = sorted({a for a in assigned if a < 1 or a > 5})
    if out_of_range:
        log(
            f"[CRITICAL] MONITOR_INDEX_OVERRIDE sai: screen_id {out_of_range} nam ngoai khoang 1-5. "
            f"Sua lai roi chay lai --dry-run."
        )
        sys.exit(1)

    if len(monitors) >= 5 and sorted(assigned) != [1, 2, 3, 4, 5]:
        log(f"[CRITICAL] Phai gan du 5 screen_id 1..5, dang gan: {sorted(assigned)}.")
        sys.exit(1)


def warn_if_monitor_widths_differ(monitors) -> None:
    """Hoat canh be ca ghep 5 man thanh 1 the gioi ao, moi man tu tinh phan cua minh dua tren
    CHIEU RONG CUA CHINH NO. Cong thuc do chi lien mach khi 5 man rong bang nhau — neu lech
    nhau, con ca se bi nhay coc o ranh gioi. Cac chuc nang khac (menu/slide/chat) khong bi
    anh huong."""
    widths = {m.width for m in monitors[:5]}
    if len(widths) > 1:
        log(
            f"[WARNING] 5 man hinh KHONG cung chieu rong ({sorted(widths)}). Hoat canh be ca o che do "
            f"cho se bi nhay coc tai ranh gioi giua cac man co kich thuoc khac nhau. "
            f"Menu, trinh chieu slide va chat van hoat dong binh thuong."
        )


def start_backend() -> subprocess.Popen:
    log("Dang khoi dong backend (uvicorn)...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=str(BACKEND_DIR),
    )
    deadline = time.time() + BACKEND_START_TIMEOUT_SEC
    while time.time() < deadline:
        if proc.poll() is not None:
            log(
                f"[CRITICAL] Backend thoat ngay khi khoi dong (exit code {proc.returncode}). "
                f"Xem backend/pentasync_log.txt de biet chi tiet."
            )
            sys.exit(1)
        try:
            with urllib.request.urlopen(HEALTHZ_URL, timeout=1) as resp:
                if resp.status == 200:
                    log("Backend da san sang.")
                    return proc
        except Exception:
            pass
        time.sleep(0.5)
    log(f"[CRITICAL] Backend khong san sang sau {BACKEND_START_TIMEOUT_SEC}s.")
    proc.terminate()
    sys.exit(1)


def launch_kiosk_windows(monitors, edge_path: str) -> list[subprocess.Popen]:
    procs = []
    for sort_index, monitor in enumerate(monitors[:5]):
        screen_id = MONITOR_INDEX_OVERRIDE.get(sort_index, sort_index + 1)
        url = f"http://{HOST}:{PORT}/screen/{screen_id}"
        user_data_dir = BACKEND_DIR / f"_edge_profile_screen_{screen_id}"
        log(
            f"Mo cua so vi tri #{sort_index} -> screen_id={screen_id} -> {url} "
            f"(x={monitor.x},y={monitor.y}, {monitor.width}x{monitor.height})"
        )
        args = [
            edge_path,
            f"--app={url}",
            f"--window-position={monitor.x},{monitor.y}",
            f"--window-size={monitor.width},{monitor.height}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--noerrdialogs",
            "--disable-infobars",
            "--disable-session-crashed-bubble",
            "--autoplay-policy=no-user-gesture-required",
        ]
        procs.append(subprocess.Popen(args))
    return procs


def main() -> None:
    parser = argparse.ArgumentParser(description="Khoi chay he thong PentaSync tren 5 man hinh vat ly.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chi do va ghi log vi tri 5 man hinh de doi chieu, KHONG khoi dong backend/trinh duyet.",
    )
    args = parser.parse_args()

    log("=== PENTASYNC LAUNCHER START ===")
    _mutex = acquire_single_instance_lock()

    monitors = detect_monitors_left_to_right()

    if args.dry_run:
        log(
            "Dry-run xong. Doi chieu log tren voi vi tri vat ly that, dien "
            "MONITOR_INDEX_OVERRIDE trong launcher.py neu thu tu sai, roi chay lai "
            "KHONG co --dry-run."
        )
        return

    edge_path = find_edge()
    backend_proc = start_backend()
    browser_procs = launch_kiosk_windows(monitors, edge_path)

    log("Tat ca da khoi chay. Nhan Ctrl+C trong cua so nay de dung toan bo he thong.")
    reported_dead: set[int] = set()
    try:
        while True:
            time.sleep(2)
            if backend_proc.poll() is not None:
                log("[CRITICAL] Backend da thoat ngoai y muon! Dang dung cac cua so con lai...")
                break
            for i, p in enumerate(browser_procs):
                if p.poll() is not None and i not in reported_dead:
                    log(f"[WARNING] Cua so man vi tri #{i} (PID {p.pid}) da dong hoac bi tat bat thuong.")
                    reported_dead.add(i)
    except KeyboardInterrupt:
        log("Nhan yeu cau dung tu ban phim...")
    finally:
        for p in browser_procs:
            if p.poll() is None:
                p.terminate()
        if backend_proc.poll() is None:
            backend_proc.terminate()
        log("=== PENTASYNC LAUNCHER STOP ===")


if __name__ == "__main__":
    main()
