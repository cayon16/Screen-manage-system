from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Awaitable, Callable

from app.logging_setup import get_logger

logger = get_logger()

OnReadyFn = Callable[[int], Awaitable[None]]

_DONE_MARKER = "done.json"


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        logger.exception("Khong tim thay ffmpeg cua imageio-ffmpeg")
        return None


def build_slice_command(ffmpeg: str, source: Path, outputs: list[Path]) -> list[str]:
    """Lenh ffmpeg cat video thanh len(outputs) lat doc bang nhau, trai -> phai.

    Giai ma 1 lan roi tach (split) ra N nhanh -> moi lat co CUNG moc thoi gian tung khung, nen
    cac man phat lat rieng van khop nhau nhu phat chung 1 file. Chieu rong lat lam tron xuong
    so chan vi H.264 yeu cau.
    """
    n = len(outputs)
    labels = "".join(f"[s{i}]" for i in range(n))
    chains = [f"[0:v]split={n}{labels}"]
    for i in range(n):
        chains.append(f"[s{i}]crop=floor(iw/{n}/2)*2:ih:floor(iw*{i}/{n}):0[o{i}]")

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
           "-filter_complex", ";".join(chains)]
    for i, out in enumerate(outputs):
        cmd += [
            "-map", f"[o{i}]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            # Khung khoa moi 2 giay: man cho hay phai tua de bat kip dong ho chung, khung khoa
            # thua thi tua mat lau.
            "-g", "60", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out),
        ]
    return cmd


class VideoSlicer:
    """Cat san video cho thanh N lat (N = so man hien thi) de moi man chi giai ma phan cua minh.

    Chay ffmpeg o tien trinh con uu tien thap; trong luc cat, cac man van phat nguyen video va tu
    dich khung (cham hon nhung cung hinh). Ket qua luu cache theo (noi dung file nguon, N): chi
    cat 1 lan cho moi cach bo tri man.
    """

    def __init__(self, source: Path, cache_dir: Path, on_ready: OnReadyFn | None = None):
        self._source = source
        self._cache_dir = cache_dir
        self._on_ready = on_ready
        self._task: asyncio.Task | None = None
        self._task_count: int | None = None
        self._process: subprocess.Popen | None = None
        self._key_cache: tuple[tuple[int, int], str] | None = None

    # ---------- truy van ----------

    def _source_key(self) -> str | None:
        """Nhận diện video nguồn theo NỘI DUNG (kích thước + 1 MiB đầu + 1 MiB cuối), không theo
        đường dẫn hay ngày sửa: chép cả thư mục sang máy khác vẫn dùng lại được lát đã cắt,
        còn thay video khác thì chắc chắn cắt lại. Kết quả nhớ theo (kích thước, ngày sửa) để
        khỏi đọc file mỗi lần hỏi."""
        try:
            stat = self._source.stat()
        except OSError:
            return None
        stamp = (stat.st_size, stat.st_mtime_ns)
        if self._key_cache is not None and self._key_cache[0] == stamp:
            return self._key_cache[1]
        digest = hashlib.sha1(str(stat.st_size).encode("ascii"))
        chunk = 1 << 20
        try:
            with self._source.open("rb") as f:
                digest.update(f.read(chunk))
                if stat.st_size > chunk:
                    f.seek(max(chunk, stat.st_size - chunk))
                    digest.update(f.read(chunk))
        except OSError:
            return None
        key = digest.hexdigest()[:16]
        self._key_cache = (stamp, key)
        return key

    def _dir_for(self, wall_count: int) -> Path | None:
        key = self._source_key()
        if key is None:
            return None
        return self._cache_dir / key / str(wall_count)

    def ready(self, wall_count: int) -> bool:
        folder = self._dir_for(wall_count)
        return folder is not None and (folder / _DONE_MARKER).is_file()

    def slice_path(self, wall_count: int, index: int) -> Path | None:
        if not 0 <= index < wall_count or not self.ready(wall_count):
            return None
        return self._dir_for(wall_count) / f"slice_{index}.mp4"

    @property
    def working_on(self) -> int | None:
        return self._task_count if self._task is not None and not self._task.done() else None

    # ---------- dieu khien ----------

    def ensure(self, wall_count: int) -> None:
        """Dam bao co lat cho `wall_count` man. Goi lai nhieu lan an toan.

        Chi chay 1 viec cat moi luc: doi bo cuc khi dang cat do thi huy viec cu — ket qua cu
        khong con ai dung.
        """
        if wall_count <= 1 or self.ready(wall_count) or self.working_on == wall_count:
            return
        self.cancel()
        self._task_count = wall_count
        self._task = asyncio.create_task(self._run(wall_count))

    def cancel(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._task_count = None

    async def _run(self, wall_count: int) -> None:
        ffmpeg = _ffmpeg_exe()
        folder = self._dir_for(wall_count)
        if ffmpeg is None or folder is None:
            logger.warning(
                "Khong cat duoc video cho (ffmpeg=%s, nguon=%s) — cac man se phat nguyen video",
                ffmpeg, self._source,
            )
            return

        self._drop_other_sources(folder.parent)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        outputs = [folder / f"slice_{i}.mp4" for i in range(wall_count)]
        cmd = build_slice_command(ffmpeg, self._source, outputs)

        logger.info("Bat dau cat video cho thanh %s lat -> %s", wall_count, folder)
        try:
            returncode, stderr = await asyncio.to_thread(self._run_process, cmd)
        except asyncio.CancelledError:
            shutil.rmtree(folder, ignore_errors=True)
            raise

        if returncode != 0:
            logger.error("Cat video cho that bai (ma %s): %s", returncode, stderr[-2000:])
            shutil.rmtree(folder, ignore_errors=True)
            return

        (folder / _DONE_MARKER).write_text(
            json.dumps({"source": str(self._source), "wall_count": wall_count}), encoding="utf-8"
        )
        logger.info("Cat video cho xong: %s lat", wall_count)
        if self._on_ready is not None:
            await self._on_ready(wall_count)

    def _run_process(self, cmd: list[str]) -> tuple[int, str]:
        # Uu tien thap: cat video la viec nen, khong duoc lam giat giao dien dang chay.
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        # Bien cuc bo: viec cat moi co the ghi de self._process trong luc luong nay con dang cho.
        process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags
        )
        self._process = process
        _, stderr = process.communicate()
        return process.returncode, stderr.decode("utf-8", errors="replace")

    def _drop_other_sources(self, keep: Path) -> None:
        """Doi video nguon thi xoa lat cua video cu — moi bo 5 lat nang ngang video goc."""
        if not self._cache_dir.is_dir():
            return
        for child in self._cache_dir.iterdir():
            if child.is_dir() and child != keep:
                shutil.rmtree(child, ignore_errors=True)
