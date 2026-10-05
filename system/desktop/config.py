"""Cấu hình của app màn hình. Cổng/địa chỉ backend và thư mục dữ liệu lấy từ
backend/app/config.py (1 nguồn duy nhất)."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import CONTENT_MANIFEST_DIR, DATA_DIR, FROZEN, HOST, PORT

DESKTOP_DIR = Path(__file__).resolve().parent
SYSTEM_DIR = DESKTOP_DIR.parent
QML_DIR = DESKTOP_DIR / "qml"
FONTS_DIR = DESKTOP_DIR / "fonts"
LOG_FILE = (DATA_DIR if FROZEN else DESKTOP_DIR) / "pentasync_app_log.txt"
MAX_LOG_SIZE = 5 * 1024 * 1024

DEFAULT_HOSPITAL_NAME = "Bệnh viện Đa khoa"


def _hospital_name() -> str:
    """Tên bệnh viện nằm trong content_manifest/slides.json ("hospital_name") — sửa được cả ở
    bản đóng gói, không phải sửa code."""
    try:
        raw = json.loads((CONTENT_MANIFEST_DIR / "slides.json").read_text(encoding="utf-8"))
        name = str(raw.get("hospital_name", "")).strip()
    except (OSError, ValueError, AttributeError):
        name = ""
    return name or DEFAULT_HOSPITAL_NAME


HOSPITAL_NAME = _hospital_name()

BACKEND_URL = f"http://{HOST}:{PORT}"
BACKEND_WS_URL = f"ws://{HOST}:{PORT}"

# Màn HDMI/DisplayPort chập chờn (TV đang bật, màn ngủ dậy) làm Windows báo rút/cắm liên tục
# trong vài giây. Chờ yên hẳn rồi mới xếp lại cửa sổ.
LAYOUT_SETTLE_MS = 3000

IDENTIFY_SECONDS = 10

# Chu kỳ chỉnh đồng bộ video chờ giữa các màn.
STANDBY_SYNC_MS = 500
