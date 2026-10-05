from __future__ import annotations

import ctypes
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QDir, QLockFile, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlEngine

from desktop.backend_process import BackendProcess
from desktop.config import BACKEND_URL, FONTS_DIR, LOG_FILE, MAX_LOG_SIZE, QML_DIR
from desktop.win32 import GlobalHotkeys
from desktop.window_manager import WindowManager

logger = logging.getLogger("pentasync.app")

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_QT_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


_QT_TEARDOWN_NOISE = ("Demuxing failed", "AV_NOPTS_VALUE", "Immediate exit requested")


def _setup_logging() -> None:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    if sys.stderr is not None:  # chạy bằng pythonw / exe thì không có console
        # Cửa sổ lệnh mặc định của Windows là cp1252, không in được chữ có dấu.
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        logger.addHandler(logging.StreamHandler())

    def qt_handler(mode, context, message):
        level = _QT_LEVELS.get(mode, logging.INFO)
        # Mỗi lần rời màn chờ, đầu phát video bị huỷ giữa lúc đang tải → FFmpeg báo lỗi ngắt kết
        # nối. Vô hại, nhưng ghi mức WARNING thì lấp mất lỗi thật trong log.
        if any(noise in message for noise in _QT_TEARDOWN_NOISE):
            level = logging.DEBUG
        # QSG_INFO in rất nhiều dòng về bộ vẽ; chỉ giữ dòng cho biết card nào được dùng.
        category = context.category or ""
        if category.startswith(("qt.rhi", "qt.scenegraph")):
            level = logging.INFO if ("Adapter" in message or "using this adapter" in message) else logging.DEBUG
        where = f" ({context.file}:{context.line})" if context.file else ""
        logger.log(level, "[qt] %s%s", message, where)

    qInstallMessageHandler(qt_handler)

    # Bản exe không có cửa sổ lệnh: lỗi Python chưa bắt (kể cả trong slot Qt) phải vào log,
    # không thì mất dấu hoàn toàn.
    def log_uncaught(exc_type, exc, tb):
        logger.critical("Lỗi chưa được xử lý", exc_info=(exc_type, exc, tb))

    sys.excepthook = log_uncaught


def _prefer_discrete_gpu() -> None:
    """Máy test có card rời (RTX 4070 Ti S, 4 màn) + đồ hoạ tích hợp (1 màn). Mặc định Windows hay
    đưa card tích hợp lên đầu → Qt vẽ + giải mã video cả 5 màn bằng chip yếu. Đặt "High
    performance" cho chính file đang chạy — đúng thiết lập mà Windows Settings → Graphics ghi ra,
    có hiệu lực ngay nếu đặt trước khi Qt khởi tạo. Đã có lựa chọn (người dùng tự đặt) thì giữ nguyên.
    """
    if sys.platform != "win32":
        return
    import winreg

    # Chạy mã nguồn trong .venv: python.exe của venv chỉ là trình khởi chạy, tiến trình thật là
    # python.exe gốc — Windows áp thiết lập theo đường dẫn của tiến trình thật.
    exe = sys.executable if getattr(sys, "frozen", False) else getattr(sys, "_base_executable", sys.executable)
    key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            try:
                value, _ = winreg.QueryValueEx(key, exe)
                logger.info("Lựa chọn card đồ hoạ có sẵn cho %s: %s", exe, value)
            except FileNotFoundError:
                winreg.SetValueEx(key, exe, 0, winreg.REG_SZ, "GpuPreference=2;")
                logger.info("Đã đặt card đồ hoạ hiệu năng cao cho %s", exe)
    except OSError:
        logger.exception("Không đặt được lựa chọn card đồ hoạ")


def _keep_displays_awake(on: bool) -> None:
    """Màn DP/HDMI ngủ là Windows gỡ nó khỏi danh sách màn và dồn cửa sổ sang màn khác.
    Giữ màn luôn thức trong suốt thời gian app chạy."""
    if sys.platform != "win32":
        return
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else 0)
    if not ctypes.windll.kernel32.SetThreadExecutionState(flags):
        logger.warning("Không đặt được chế độ giữ màn luôn thức")


def _load_fonts(app: QGuiApplication) -> None:
    for path in sorted(FONTS_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            logger.warning("Không nạp được phông %s", path.name)
    app.setFont(QFont("Be Vietnam Pro"))


def main() -> int:
    _setup_logging()
    _prefer_discrete_gpu()
    # Ghi vào log card đồ hoạ mà Qt dùng để vẽ (máy test có cả card rời lẫn đồ hoạ tích hợp).
    os.environ.setdefault("QSG_INFO", "1")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("PentaSync")
    # Cắm/rút màn sẽ đóng rồi mở lại cửa sổ — không được coi là "đóng hết cửa sổ thì thoát".
    app.setQuitOnLastWindowClosed(False)

    lock = QLockFile(os.path.join(QDir.tempPath(), "pentasync-app.lock"))
    if not lock.tryLock(200):
        logger.error("PentaSync đang chạy rồi — không mở bản thứ hai")
        return 1

    logger.info("===== PentaSync khởi động (backend %s) =====", BACKEND_URL)
    _load_fonts(app)
    _keep_displays_awake(True)

    backend = BackendProcess()
    engine = QQmlEngine()
    engine.addImportPath(str(QML_DIR))
    manager = WindowManager(app, engine, backend)

    # Phím tắt ăn cả khi cửa sổ app không được chọn (vd vừa bấm sang chương trình khác).
    hotkeys = GlobalHotkeys()
    app.installNativeEventFilter(hotkeys)
    combos = [hotkeys.register(key, action) for key, action in
              (("M", manager.toggleManagement), ("I", manager.identify), ("Q", manager.quit))]
    logger.info("Phím tắt: bảng điều khiển %s · nhận diện màn %s · thoát %s", *combos)

    def shutdown() -> None:
        logger.info("PentaSync đang tắt")
        hotkeys.unregister_all()
        manager.shutdown()
        backend.stop()
        _keep_displays_awake(False)

    app.aboutToQuit.connect(shutdown)

    # Ctrl+C trong cửa sổ lệnh: Python chỉ xử lý tín hiệu khi được chạy — cho nó chạy định kỳ.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    pulse = QTimer()
    pulse.start(300)
    pulse.timeout.connect(lambda: None)

    backend.start()
    manager.start()
    code = app.exec()
    lock.unlock()
    return code
