"""Đóng gói PentaSync → system/dist/PentaSync/PentaSync.exe (máy chạy không cần cài Python).

Chạy từ thư mục system/:
    .venv\\Scripts\\python -m pip install pyinstaller
    .venv\\Scripts\\python packaging\\build.py

Kết quả (chép nguyên thư mục dist/PentaSync sang máy khác là chạy):
    PentaSync.exe
    _internal/            mã chương trình — đừng sửa
    content_manifest/     nội dung slide + tên bệnh viện (slides.json) — SỬA ĐƯỢC
    video/                video chờ — chép đè file cùng tên để đổi video
    data/                 database, log, lát video đã cắt sẵn — máy tự sinh
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Cửa sổ lệnh mặc định của Windows dùng cp1252 — in chữ có dấu sẽ làm script chết ở dòng tổng kết.
for _luong in (sys.stdout, sys.stderr):
    if hasattr(_luong, "reconfigure"):
        _luong.reconfigure(encoding="utf-8", errors="replace")

SYSTEM = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SYSTEM / "backend")]

from app.config import STANDBY_SLICE_CACHE_DIR, STANDBY_VIDEO_PATH, STANDBY_VIDEO_REL_PATH  # noqa: E402

DIST = SYSTEM / "dist"
OUT = DIST / "PentaSync"


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def _size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 2**20


def main() -> int:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DIST), "--workpath", str(SYSTEM / "build"),
         str(SYSTEM / "packaging" / "PentaSync.spec")],
        check=True,
    )

    _copytree(SYSTEM / "backend" / "content_manifest", OUT / "content_manifest")

    if STANDBY_VIDEO_PATH.is_file():
        target = OUT / STANDBY_VIDEO_REL_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(STANDBY_VIDEO_PATH, target)
    else:
        print(f"CẢNH BÁO: không thấy video chờ {STANDBY_VIDEO_PATH} — nhớ chép vào {OUT / STANDBY_VIDEO_REL_PATH}")

    # Lát video đã cắt trên máy build → máy chạy khỏi phải cắt lại (mất vài phút).
    if STANDBY_SLICE_CACHE_DIR.is_dir():
        _copytree(STANDBY_SLICE_CACHE_DIR, OUT / "data" / "_cache" / "standby_slices")

    for doc in ("HUONG_DAN_TEST.md", "README.md", "descryption.md"):
        if (SYSTEM / doc).is_file():
            shutil.copy2(SYSTEM / doc, OUT / doc)
    shutil.copy2(SYSTEM / "packaging" / "chay_thu_nhanh.bat", OUT / "chay_thu_nhanh.bat")

    print(f"\nXong: {OUT / 'PentaSync.exe'}")
    print(f"  chương trình  {_size_mb(OUT / '_internal'):7.0f} MB")
    for name in ("content_manifest", "video", "data"):
        if (OUT / name).exists():
            print(f"  {name:<13} {_size_mb(OUT / name):7.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
