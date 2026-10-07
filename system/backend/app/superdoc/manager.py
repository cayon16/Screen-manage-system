"""Quan ly ket noi AI luc dang chay: doi che do khong can khoi dong lai, thu ket noi truoc khi doi,
theo doi tinh trang de bang dieu khien hien.

Moi phien chat "muon" 1 provider qua acquire() va giu den khi dong (AiLease): doi AI giua chung thi
chat moi dung AI moi, chat dang do van dung AI cu — chatbot noi bo co the giu phien phia no.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import uuid4

from app.config import SUPERDOC_SYSTEM_PROMPT, SUPERDOC_TIMEOUT_SEC
from app.logging_setup import get_logger
from app.superdoc import registry
from app.superdoc.base import ChatContext, SuperdocError, SuperdocProvider, Turn
from app.superdoc.registry import ProviderConfigError
from app.superdoc.settings import AiSettings, load_settings, save_settings
from app.superdoc.unavailable_provider import UnavailableProvider

logger = get_logger()

OnChangeFn = Callable[[], Awaitable[None]]

PROBE_TEXT = "Đây là tin nhắn kiểm tra kết nối. Hãy trả lời ngắn: OK."
# Qua ngan nay lien tiep khong thanh cong thi coi la mat ket noi (1-2 lan: chi suy giam).
DOWN_AFTER_FAILURES = 3


class AiTestFailed(Exception):
    """Thu ket noi truoc khi doi that bai — AI cu van giu nguyen."""

    def __init__(self, result: dict):
        super().__init__("Thử kết nối thất bại")
        self.result = result


class _Status:
    """Tinh trang ket noi cua AI dang dung (chia se giua cac lan doi cau hinh de dem theo ngay)."""

    def __init__(self) -> None:
        self.day = date.today()
        self.calls_today = 0
        self.errors_today = 0
        self.last_test: dict | None = None
        self.reset_connection()

    def reset_connection(self) -> None:
        self.state = "unknown"  # unknown | ok | degraded | down
        self.last_ok_at: float | None = None
        self.last_latency_ms: int | None = None
        self.last_error: dict | None = None
        self.consecutive_failures = 0

    def _roll_day(self) -> None:
        if date.today() != self.day:
            self.day = date.today()
            self.calls_today = 0
            self.errors_today = 0

    def record_ok(self, latency_ms: int) -> None:
        self._roll_day()
        self.calls_today += 1
        self.state = "ok"
        self.last_ok_at = time.time()
        self.last_latency_ms = latency_ms
        self.consecutive_failures = 0

    def record_error(self, code: str, message: str) -> None:
        self._roll_day()
        self.calls_today += 1
        self.errors_today += 1
        self.consecutive_failures += 1
        self.state = "down" if self.consecutive_failures >= DOWN_AFTER_FAILURES else "degraded"
        self.last_error = {"at": time.time(), "code": code, "message": message}

    def mark_down(self, code: str, message: str) -> None:
        """Cau hinh sai ngay tu dau: chua co cuoc goi nao nhung da biet la khong dung duoc."""
        self.state = "down"
        self.last_error = {"at": time.time(), "code": code, "message": message}

    def key(self) -> tuple[str, str | None]:
        return self.state, (self.last_error or {}).get("code")

    def as_dict(self) -> dict:
        self._roll_day()
        return {
            "state": self.state,
            "last_ok_at": self.last_ok_at,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "calls_today": self.calls_today,
            "errors_today": self.errors_today,
            "last_test": self.last_test,
        }


class _Tracked:
    """Boc provider that de do do tre va dem loi. Chi ghi nhan khi con la AI dang dung (`live`):
    provider cu dang cho phien cuoi dong khong duoc lam sai tinh trang cua AI moi."""

    def __init__(self, inner: SuperdocProvider, status: _Status, notify: Callable[[], Awaitable[None]]):
        self.inner = inner
        self.live = True
        self._status = status
        self._notify = notify

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str | None:
        # FakeProvider trong test khong co thuoc tinh model.
        return getattr(self.inner, "model", None)

    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str:
        started = time.monotonic()
        try:
            text = await self.inner.reply(history, context)
        except asyncio.CancelledError:
            raise
        except SuperdocError as exc:
            await self._record_error(exc.code, str(exc))
            raise
        except Exception:
            await self._record_error("error", "Lỗi không lường trước khi gọi AI")
            raise
        if self.live:
            before = self._status.key()
            self._status.record_ok(int((time.monotonic() - started) * 1000))
            await self._notify_if_changed(before)
        return text

    def note_timeout(self) -> None:
        """ChatSession tu ngat cuoc goi khi qua han, nen provider khong biet minh da cham: phien chat
        bao lai cho day. Khong thong bao ngay (ham dong bo) — lan doi trang thai ke tiep se hien."""
        if self.live:
            self._status.record_error("timeout", "AI không trả lời kịp trong thời gian cho phép")

    async def end_session(self, context: ChatContext, reason: str) -> None:
        await self.inner.end_session(context, reason)

    async def aclose(self) -> None:
        await self.inner.aclose()

    async def _record_error(self, code: str, message: str) -> None:
        if not self.live:
            return
        before = self._status.key()
        self._status.record_error(code, message)
        await self._notify_if_changed(before)

    async def _notify_if_changed(self, before: tuple[str, str | None]) -> None:
        # Chi bao bang dieu khien khi cai nguoi van hanh nhin thay doi (tinh trang / ma loi),
        # khong bao moi cau tra loi thanh cong.
        if self._status.key() != before:
            await self._notify()


class AiLease:
    """Phien chat muon 1 provider tu luc mo den luc dong. release() goi nhieu lan van an toan."""

    def __init__(self, provider: _Tracked, system_prompt: str, timeout_sec: float,
                 release: Callable[[_Tracked], None]):
        self.provider = provider
        self.system_prompt = system_prompt
        self.timeout_sec = timeout_sec
        self._release = release
        self._released = False

    def note_timeout(self) -> None:
        self.provider.note_timeout()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._release(self.provider)


class AiManager:
    def __init__(self, settings_path: Path | None, env: Mapping[str, str] = os.environ,
                 on_change: OnChangeFn | None = None):
        self._path = settings_path
        self._env = env
        self._on_change = on_change
        self._settings = AiSettings()
        self._status = _Status()
        self._active: _Tracked | None = None
        self._pins: dict[_Tracked, int] = {}
        self._retiring: set[_Tracked] = set()
        self._closing: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        # Che do co dinh (test): khong doc/ghi file, khong doi duoc.
        self._fixed = False
        self._fixed_prompt = SUPERDOC_SYSTEM_PROMPT
        self._fixed_timeout = SUPERDOC_TIMEOUT_SEC

    @classmethod
    def fixed(cls, provider: SuperdocProvider, system_prompt: str = SUPERDOC_SYSTEM_PROMPT,
              timeout_sec: float = SUPERDOC_TIMEOUT_SEC) -> "AiManager":
        manager = cls(None)
        manager._fixed = True
        manager._fixed_prompt = system_prompt
        manager._fixed_timeout = timeout_sec
        manager._active = _Tracked(provider, manager._status, manager._notify)
        return manager

    async def start(self) -> None:
        if self._fixed:
            return
        self._settings = load_settings(self._path, self._env)
        try:
            provider = registry.build(self._settings, self._env)
        except ProviderConfigError as exc:
            # CO Y khong lui ve mock: tra loi bang du lieu gia tren man hinh benh vien nguy hiem hon
            # la bao that "chua ket noi duoc".
            logger.error("Cau hinh AI chua dung (%s) — chat se bao loi cho toi khi sua: %s", exc.field, exc.message)
            provider = UnavailableProvider(exc.message)
            self._status.mark_down("not_configured", exc.message)
        except Exception:
            logger.exception("Khong dung duoc provider AI — chat se bao loi cho toi khi sua cau hinh")
            provider = UnavailableProvider("Không khởi tạo được kết nối AI (xem log)")
            self._status.mark_down("not_configured", "Không khởi tạo được kết nối AI (xem log)")
        self._active = _Tracked(provider, self._status, self._notify)
        info = registry.describe(self._settings, self._env)
        logger.info("Superdoc AI: che do=%s nha cung cap=%s model=%s", info["mode"], info["provider"], info["model"])

    # ---------- cho phien chat ----------

    def acquire(self) -> AiLease:
        """DONG BO, khong await: goi trong hang doi command nen khong duoc phep cho."""
        tracked = self._active
        if tracked is None:
            raise RuntimeError("AiManager chua start()")
        self._pins[tracked] = self._pins.get(tracked, 0) + 1
        if self._fixed:
            prompt, timeout = self._fixed_prompt, self._fixed_timeout
        else:
            prompt = self._settings.system_prompt or SUPERDOC_SYSTEM_PROMPT
            timeout = self._settings.timeout_sec
        return AiLease(tracked, prompt, timeout, self._release)

    def _release(self, tracked: _Tracked) -> None:
        left = self._pins.get(tracked, 0) - 1
        if left > 0:
            self._pins[tracked] = left
            return
        self._pins.pop(tracked, None)
        if tracked in self._retiring:
            self._retiring.discard(tracked)
            self._close_later(tracked)

    def _close_later(self, tracked: _Tracked) -> None:
        task = asyncio.get_running_loop().create_task(tracked.aclose())
        self._closing.add(task)
        task.add_done_callback(self._closing.discard)

    # ---------- doi cau hinh ----------

    async def apply(self, settings: AiSettings, *, test_first: bool = True) -> dict[str, Any]:
        """Doi sang cau hinh moi. Thieu thu gi -> ProviderConfigError; thu ket noi hong -> AiTestFailed.
        Ca hai deu giu nguyen AI dang dung."""
        if self._fixed:
            raise RuntimeError("AiManager che do co dinh khong doi duoc")
        async with self._lock:
            found = registry.problems(settings, self._env)
            if found:
                raise found[0]
            provider = registry.build(settings, self._env)
            result = None
            if test_first:
                result = await self._probe(provider, settings)
                if not result["ok"]:
                    await provider.aclose()
                    self._status.last_test = result
                    raise AiTestFailed(result)
            self._swap(provider, settings)
            self._status.last_test = result
            saved = self._save(settings)
        await self._notify()
        return {
            "applied": True,
            "saved": saved,
            "active": registry.describe(settings, self._env),
            "test": result,
            "pinned_sessions": self._pinned_sessions(),
        }

    async def set_mode(self, mode: str, *, test_first: bool = True) -> dict[str, Any]:
        """Doi che do, giu nguyen phan cau hinh con lai."""
        settings = AiSettings.model_validate({**self._settings.model_dump(), "mode": mode})
        return await self.apply(settings, test_first=test_first)

    async def test(self, settings: AiSettings | None = None) -> dict[str, Any]:
        """Thu 1 cau. Khong tinh vao so cuoc goi/loi trong ngay (do la viec cua nguoi van hanh)."""
        async with self._lock:
            if settings is None:
                tracked = self._active
                if tracked is None:
                    raise RuntimeError("AiManager chua start()")
                result = await self._probe(tracked.inner, self._settings_for_probe())
            else:
                found = registry.problems(settings, self._env)
                if found:
                    raise found[0]
                provider = registry.build(settings, self._env)
                try:
                    result = await self._probe(provider, settings)
                finally:
                    await provider.aclose()
            self._status.last_test = result
        await self._notify()
        return result

    def _settings_for_probe(self) -> AiSettings:
        if self._fixed:
            return AiSettings.model_construct(timeout_sec=self._fixed_timeout, system_prompt=self._fixed_prompt)
        return self._settings

    async def _probe(self, provider: SuperdocProvider, settings: AiSettings) -> dict[str, Any]:
        ctx = ChatContext(f"test-{uuid4()}", 0, settings.system_prompt or SUPERDOC_SYSTEM_PROMPT)
        started = time.monotonic()
        result: dict[str, Any]
        try:
            text = await asyncio.wait_for(
                provider.reply([Turn("user", PROBE_TEXT)], ctx), timeout=settings.timeout_sec
            )
            result = {"ok": True, "reply_preview": text[:200]}
        except asyncio.TimeoutError:
            result = {"ok": False, "error": {"code": "timeout", "message": "AI không trả lời kịp trong thời gian cho phép"}}
        except SuperdocError as exc:
            result = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        except Exception:
            logger.exception("Loi khong luong truoc khi thu ket noi AI")
            result = {"ok": False, "error": {"code": "error", "message": "Lỗi không lường trước (xem log)"}}
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["provider"] = provider.name
        result["model"] = getattr(provider, "model", None)
        result["at"] = time.time()
        try:
            await provider.end_session(ctx, "connection_test")
        except Exception as exc:
            logger.warning("Bao ket thuc phien thu cho AI that bai: %s", type(exc).__name__)
        return result

    def _swap(self, provider: SuperdocProvider, settings: AiSettings) -> None:
        old = self._active
        self._active = _Tracked(provider, self._status, self._notify)
        self._settings = settings
        self._status.reset_connection()
        if old is None:
            return
        old.live = False
        if self._pins.get(old, 0) == 0:
            self._close_later(old)
        else:
            self._retiring.add(old)
        info = registry.describe(settings, self._env)
        logger.info("Doi AI: che do=%s nha cung cap=%s model=%s (%s chat dang dung AI cu)",
                    info["mode"], info["provider"], info["model"], self._pinned_sessions())

    def _save(self, settings: AiSettings) -> bool:
        if self._path is None:
            return False
        try:
            save_settings(self._path, settings)
        except OSError:
            logger.exception("Khong luu duoc cau hinh AI — AI da doi nhung lan khoi dong sau se mat")
            return False
        return True

    def _pinned_sessions(self) -> int:
        """So phien chat dang giu AI cu (chua tinh phien dang dung AI hien tai)."""
        return sum(self._pins.get(t, 0) for t in self._retiring)

    # ---------- doc trang thai ----------

    def snapshot(self) -> dict[str, Any]:
        """Cho GET /api/ai. KHONG BAO GIO chua gia tri key — chi bao co/chua co."""
        if self._fixed:
            tracked = self._active
            active = {"mode": "demo", "provider": tracked.name, "model": tracked.model, "base_url": None}
            problems: list[ProviderConfigError] = []
        else:
            active = registry.describe(self._settings, self._env)
            problems = registry.problems(self._settings, self._env)
        return {
            "active": active,
            "settings": self._settings.model_dump(),
            "secrets": {name: bool(self._env.get(name, "").strip()) for name in registry.SECRET_ENV_NAMES},
            "status": self._status.as_dict(),
            "problems": [{"field": p.field, "message": p.message} for p in problems],
            "pinned_sessions": self._pinned_sessions(),
            "catalog": registry.CATALOG,
        }

    def brief(self) -> dict[str, Any]:
        """Ban rut gon cho bang dieu khien."""
        snap = self.snapshot()
        active, status = snap["active"], snap["status"]
        return {
            "mode": active["mode"],
            "provider": active["provider"],
            "model": active["model"],
            "state": status["state"],
            "last_error_code": (status["last_error"] or {}).get("code"),
        }

    async def _notify(self) -> None:
        if self._on_change is None:
            return
        try:
            await self._on_change()
        except Exception:
            logger.exception("Bao thay doi AI cho bang dieu khien that bai")

    async def aclose(self) -> None:
        providers = [t for t in (self._active, *self._retiring) if t is not None]
        self._active = None
        self._retiring.clear()
        await asyncio.gather(*(p.aclose() for p in providers), *self._closing, return_exceptions=True)
