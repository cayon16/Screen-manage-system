from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import DB_PATH
from app.logging_setup import get_logger

logger = get_logger()

# Luu toan bo lich su tro chuyen theo yeu cau descryption.txt muc 3.
# KHONG luu bat ky thong tin dinh danh nao — moi phien chat deu la "khach la" (khong ten, khong
# so dien thoai, khong IP). Ban ghi chi gom: man nao, luc nao, ai noi gi.
#
# Luu y ve tu "xoa sach lich su chat" trong dac ta: do la xoa lich su TRONG BO NHO (ngu canh gui
# cho AI + noi dung hien tren man), de nguoi ke tiep khong doc duoc cuoc tro chuyen cua nguoi
# truoc. Ban ghi trong database van duoc giu lai — day chinh la yeu cau "luu toan bo lich su".

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id  TEXT PRIMARY KEY,
    screen_id   INTEGER NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    end_reason  TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ChatStore:
    """Luu lich su chat vao SQLite.

    Moi thao tac mo 1 connection rieng roi dong ngay: SQLite mac dinh gan connection voi thread
    tao ra no, ma cac lenh o day chay qua asyncio.to_thread (thread bat ky trong pool). Voi khoi
    luong that te (vai tin nhan moi phien chat) chi phi mo connection la khong dang ke, doi lai
    khong phai tu quan ly lock giua cac thread.
    """

    def __init__(self, db_path: Path | str = DB_PATH):
        self._db_path = str(db_path)

    # ---------- phan chay dong bo (trong thread) ----------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _open_session_sync(self, session_id: str, screen_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO chat_sessions (session_id, screen_id, started_at) VALUES (?, ?, ?)",
                (session_id, screen_id, _utc_now()),
            )

    def _add_message_sync(self, session_id: str, role: str, text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, text, _utc_now()),
            )

    def _close_session_sync(self, session_id: str, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_sessions SET ended_at = ?, end_reason = ? WHERE session_id = ?",
                (_utc_now(), reason, session_id),
            )

    # ---------- API bat dong bo dung trong backend ----------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)
        logger.info("ChatStore san sang tai %s", self._db_path)

    async def open_session(self, session_id: str, screen_id: int) -> None:
        await self._guarded(self._open_session_sync, session_id, screen_id)

    async def add_message(self, session_id: str, role: str, text: str) -> None:
        await self._guarded(self._add_message_sync, session_id, role, text)

    async def close_session(self, session_id: str, reason: str) -> None:
        await self._guarded(self._close_session_sync, session_id, reason)

    async def _guarded(self, fn, *args) -> None:
        """Ghi log that bai nhung KHONG nem tiep: mat 1 ban ghi lich su khong duoc phep lam sap
        phien chat cua benh nhan dang dung man hinh."""
        try:
            await asyncio.to_thread(fn, *args)
        except Exception:
            logger.exception("Ghi database that bai: %s%r", fn.__name__, args)

    # ---------- thong ke cho man quan ly ----------

    def _stats_since_sync(self, since_iso: str) -> tuple[int, float | None]:
        with self._connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE started_at >= ?", (since_iso,)
            ).fetchone()[0]
            avg = conn.execute(
                "SELECT AVG((julianday(ended_at) - julianday(started_at)) * 86400.0) "
                "FROM chat_sessions WHERE started_at >= ? AND ended_at IS NOT NULL",
                (since_iso,),
            ).fetchone()[0]
        return int(count), (float(avg) if avg is not None else None)

    async def stats_since(self, since: datetime) -> tuple[int, float | None]:
        """(so phien chat bat dau tu `since`, thoi luong trung binh giay cua cac phien da dong)."""
        since_iso = since.astimezone(timezone.utc).isoformat(timespec="seconds")
        try:
            return await asyncio.to_thread(self._stats_since_sync, since_iso)
        except Exception:
            logger.exception("Doc thong ke that bai")
            return 0, None

    # ---------- doc lai (dung cho test va cong cu tra cuu sau nay) ----------

    def fetch_messages(self, session_id: str) -> list[tuple[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, text FROM chat_messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def fetch_session(self, session_id: str) -> tuple | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT session_id, screen_id, started_at, ended_at, end_reason "
                "FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
