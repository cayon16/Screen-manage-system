from __future__ import annotations

import os
import sys


def run_backend() -> int:
    # Bản exe không có cửa sổ lệnh: Python có thể để stdout/stderr = None, và uvicorn sẽ chết ngay
    # lần đầu ghi log. Hướng về "hư không" cho an toàn (log chi tiết đã có trong file của backend).
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 (mở suốt đời tiến trình)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 (mở suốt đời tiến trình)

    import uvicorn

    from app.config import HOST, PORT
    from app.main import app

    # Backend tự ghi log chi tiết vào file log của nó; ở đây chỉ để lọt cảnh báo/lỗi
    # (app đọc lại và chép vào log của app).
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    return 0
