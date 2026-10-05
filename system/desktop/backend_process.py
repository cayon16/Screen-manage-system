"""Chạy backend FastAPI làm tiến trình con và canh cho nó luôn sống.

- Backend chết → tự khởi động lại (chờ tăng dần tới 10 giây).
- Hỏi /healthz mỗi giây; mỗi lần backend vừa sẵn sàng (kể cả sau khi khởi động lại) thì phát
  `ready` — backend mới chưa biết bố cục màn, app phải gửi lại.
- Tiến trình con gắn vào 1 Job Object của Windows: app chết kiểu gì (kể cả bị tắt từ Task
  Manager) thì backend cũng chết theo, không để lại tiến trình mồ côi giữ cổng 8000.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes as w

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from desktop.config import BACKEND_URL, DESKTOP_DIR, SYSTEM_DIR

logger = logging.getLogger("pentasync.app")

HEALTH_INTERVAL_MS = 1000
HEALTH_FAILS_BEFORE_LOST = 3
RESTART_MIN_MS = 1000
RESTART_MAX_MS = 10000


def backend_command() -> tuple[str, list[str]]:
    if getattr(sys, "frozen", False):
        return sys.executable, ["--backend"]
    return sys.executable, [str(DESKTOP_DIR / "run.py"), "--backend"]


class _KillOnCloseJob:
    """Windows Job Object với cờ KILL_ON_JOB_CLOSE."""

    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", w.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", w.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", w.DWORD),
            ("SchedulingClass", w.DWORD),
        ]

    class _EXTENDED(ctypes.Structure):
        pass

    _EXTENDED._fields_ = [  # noqa: RUF012 (ctypes doi dung list)
        ("BasicLimitInformation", _BASIC),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]

    def __init__(self):
        self._job = None
        if sys.platform != "win32":
            return
        k32 = ctypes.windll.kernel32
        k32.CreateJobObjectW.restype = w.HANDLE
        k32.OpenProcess.restype = w.HANDLE
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return
        info = self._EXTENDED()
        info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(
            w.HANDLE(job), self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info),
        )
        if ok:
            self._job = job
        else:
            k32.CloseHandle(w.HANDLE(job))

    def add(self, pid: int) -> None:
        if not self._job or not pid:
            return
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(self.PROCESS_SET_QUOTA | self.PROCESS_TERMINATE, False, pid)
        if not handle:
            return
        if not k32.AssignProcessToJobObject(w.HANDLE(self._job), w.HANDLE(handle)):
            logger.warning("Không gắn được backend vào Job Object (pid %s)", pid)
        k32.CloseHandle(w.HANDLE(handle))


class BackendProcess(QObject):
    ready = Signal()
    lost = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._job = _KillOnCloseJob()
        self._process: QProcess | None = None
        self._stopping = False
        self._is_ready = False
        self._fails = 0
        self._restart_ms = RESTART_MIN_MS

        self._net = QNetworkAccessManager(self)
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(HEALTH_INTERVAL_MS)
        self._health_timer.timeout.connect(self._check_health)
        self._pending: QNetworkReply | None = None

        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._spawn)

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def start(self) -> None:
        self._stopping = False
        self._spawn()
        self._health_timer.start()

    def stop(self) -> None:
        self._stopping = True
        self._health_timer.stop()
        self._restart_timer.stop()
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        process.terminate()
        # Backend không có cửa sổ nên thường không phản hồi lệnh đóng êm — đừng bắt người dùng chờ lâu.
        if not process.waitForFinished(1000):
            process.kill()
            process.waitForFinished(2000)

    # ---------- tiến trình ----------

    def _spawn(self) -> None:
        if self._stopping:
            return
        program, args = backend_command()
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(SYSTEM_DIR))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self._drain(process))
        process.finished.connect(lambda code, status: self._on_finished(process, code, status))
        process.errorOccurred.connect(self._on_error)
        logger.info("Khởi động backend: %s %s", program, " ".join(args))
        process.start(program, args)
        if process.waitForStarted(5000):
            self._job.add(int(process.processId()))
        self._process = process

    def _on_error(self, error) -> None:
        # Tắt app thì chính ta giết backend — Qt báo "Crashed", không phải lỗi thật.
        if not self._stopping:
            logger.error("Backend lỗi tiến trình: %s", error)

    def _drain(self, process: QProcess) -> None:
        text = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.strip():
                logger.info("[backend] %s", line)

    def _on_finished(self, process: QProcess, code: int, status) -> None:
        if process is not self._process:
            return
        self._drain(process)
        self._set_ready(False)
        if self._stopping:
            return
        logger.error("Backend dừng bất thường (mã %s) — khởi động lại sau %s ms", code, self._restart_ms)
        self._restart_timer.start(self._restart_ms)
        self._restart_ms = min(self._restart_ms * 2, RESTART_MAX_MS)

    # ---------- kiểm tra sức khoẻ ----------

    def _check_health(self) -> None:
        if self._pending is not None:
            return
        request = QNetworkRequest(QUrl(f"{BACKEND_URL}/healthz"))
        request.setTransferTimeout(HEALTH_INTERVAL_MS)
        reply = self._net.get(request)
        self._pending = reply
        reply.finished.connect(lambda: self._on_health(reply))

    def _on_health(self, reply: QNetworkReply) -> None:
        self._pending = None
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        reply.deleteLater()
        if ok:
            self._fails = 0
            self._restart_ms = RESTART_MIN_MS
            self._set_ready(True)
            return
        self._fails += 1
        if self._fails >= HEALTH_FAILS_BEFORE_LOST:
            self._set_ready(False)

    def _set_ready(self, value: bool) -> None:
        if value == self._is_ready:
            return
        self._is_ready = value
        if value:
            logger.info("Backend sẵn sàng")
            self.ready.emit()
        else:
            self.lost.emit()
