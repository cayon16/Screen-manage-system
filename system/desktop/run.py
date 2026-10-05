"""Điểm chạy duy nhất của PentaSync.

    python desktop/run.py            → mở app màn hình (tự chạy backend làm tiến trình con)
    python desktop/run.py --backend  → chỉ chạy backend (app tự gọi, không cần gõ tay)
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

DEFAULT_PORT = 8000


def _setup_path() -> None:
    system_dir = Path(__file__).resolve().parent.parent
    for path in (system_dir / "backend", system_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _choose_port() -> None:
    """Có chương trình khác đang dùng cổng 8000 thì backend không khởi động được và mọi màn đứng
    ở "Đang kết nối". Chọn cổng trống khác; backend (tiến trình con) nhận lại qua biến môi trường.
    Phải chạy TRƯỚC khi nạp cấu hình (app.config đọc biến này lúc nạp)."""
    if os.environ.get("PENTASYNC_PORT"):
        return
    if _port_in_use(DEFAULT_PORT):
        os.environ["PENTASYNC_PORT"] = str(_free_port())


def main() -> int:
    _setup_path()
    if "--backend" in sys.argv:
        from desktop.backend_entry import run_backend

        return run_backend()

    _choose_port()
    from desktop.main import main as run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
