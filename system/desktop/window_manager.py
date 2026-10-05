"""Mở đúng cửa sổ trên đúng màn, và xếp lại khi màn được cắm/rút.

Mỗi màn hiển thị = 1 cửa sổ QML toàn màn hình gắn với 1 QScreen. Qt tự lo DPI từng màn nên
chỉ cần `setScreen + setGeometry(screen.geometry()) + showFullScreen()` là khớp mép tuyệt đối
— không tự tính toạ độ (nguyên nhân lỗi lệch màn của bản Edge cũ).

Không tin mù: sau khi đặt, và định kỳ 5 giây, app hỏi thẳng Windows khung thật của từng cửa sổ
(pixel vật lý) và so với khung màn. Lệch thì đặt lại bằng Qt; lệch lần nữa thì ép bằng Win32.
Mọi kết quả đều ghi log để kiểm tra tại chỗ.
"""

from __future__ import annotations

import json
import logging
import time

from PySide6.QtCore import (
    Property,
    QByteArray,
    QEvent,
    QObject,
    QRect,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QEventPoint, QGuiApplication, QScreen, QWindow
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow

from desktop import telex, win32
from desktop.admin_client import AdminClient
from desktop.backend_process import BackendProcess
from desktop.config import BACKEND_URL, HOSPITAL_NAME, IDENTIFY_SECONDS, LAYOUT_SETTLE_MS, QML_DIR
from desktop.layout import ROLE_NAMES, Assignment, assign
from desktop.monitors import ScreenEntry, read_screens, touch_devices, touch_problem
from desktop.screen_client import ScreenClient
from desktop.standby_sync import StandbySync

logger = logging.getLogger("pentasync.app")

TOUCH_ROLES = (2, 4)
WINDOWED_MANAGEMENT_SIZE = (1280, 720)
GUARD_INTERVAL_MS = 5000
# Kiểm vị trí ngay sau khi xếp: lần sớm để sửa sớm, lần sau để ghi báo cáo khi mọi thứ đã yên.
PLACEMENT_CHECKS_MS = (700, 2500)


class _WakeOnPress(QObject):
    """Màn 2/4: chạm vào BẤT KỲ đâu cũng báo backend (đánh thức, giữ phiên chat còn sống) —
    kể cả khi chạm trúng nút hay bàn phím. Không nuốt sự kiện: nút vẫn nhận chạm như thường."""

    def __init__(self, client: ScreenClient, parent: QObject | None = None):
        super().__init__(parent)
        self._client = client
        self._last = 0.0

    def eventFilter(self, obj, event) -> bool:
        if _is_press(event):
            now = time.monotonic()
            # Một lần chạm có thể đến dưới 2 dạng (cảm ứng + chuột giả lập) — chỉ tính 1.
            if now - self._last > 0.15:
                self._last = now
                self._client.touch("generic_wake")
        return False


def _is_press(event) -> bool:
    """Có ngón tay / nút chuột VỪA nhấn xuống trong sự kiện này không.

    Không được chỉ nhìn TouchBegin: Qt gộp mọi màn cảm ứng thành 1 thiết bị, nên khi màn 2 đang có
    ngón tay đặt mà màn 4 bị chạm, màn 4 nhận TouchUpdate có điểm "Pressed" chứ không phải
    TouchBegin (đã đo bằng chạm giả của Windows). Qt Quick xử lý theo trạng thái từng điểm nên nút
    vẫn ăn — bộ lọc này cũng phải làm y như vậy.
    """
    kind = event.type()
    if kind == QEvent.Type.MouseButtonPress:
        return True
    if kind in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate):
        return any(p.state() == QEventPoint.State.Pressed for p in event.points())
    return False


class TelexBridge(QObject):
    """Cho bàn phím QML gọi bộ gõ Telex (desktop/telex.py)."""

    @Slot(str, str, result=str)
    def typeKey(self, text: str, key: str) -> str:
        return telex.type_key(text, key)

    @Slot(str, result=str)
    def erase(self, text: str) -> str:
        return telex.backspace(text)


class _DisplaySlot:
    def __init__(self, role: int, window: QQuickWindow, client: ScreenClient, sync: StandbySync):
        self.role = role
        self.window = window
        self.client = client
        self.sync = sync

    def close(self) -> None:
        self.sync.detach()
        self.client.close()
        self.window.close()
        self.window.deleteLater()
        self.client.deleteLater()
        self.sync.deleteLater()


def _place_fullscreen(window: QQuickWindow, screen: QScreen, force: bool = False) -> None:
    already = (
        window.isVisible()
        and window.screen() == screen
        and window.visibility() == QWindow.Visibility.FullScreen
        and window.geometry() == screen.geometry()
    )
    if already and not force:
        return
    if window.isVisible():
        # Chuyển cửa sổ đang toàn màn hình sang màn khác: thoát toàn màn hình trước, nếu không
        # Windows giữ khung của màn cũ.
        window.showNormal()
    window.setScreen(screen)
    window.setGeometry(screen.geometry())
    window.showFullScreen()


class _Target:
    """1 cửa sổ toàn màn hình và màn nó phải phủ kín."""

    def __init__(self, label: str, window: QQuickWindow, entry: ScreenEntry, topmost: bool,
                 giu_tren_cung: bool = True):
        self.label = label
        self.window = window
        self.entry = entry
        self.topmost = topmost
        # Màn hiển thị phải luôn thấy được; màn quản lý thì không (người vận hành còn dùng máy).
        self.keep_visible = giu_tren_cung
        self.misses = 0


class WindowManager(QObject):
    displaysChanged = Signal()
    identifyChanged = Signal()
    managementChanged = Signal()
    touchWarningChanged = Signal()

    def __init__(self, app: QGuiApplication, engine: QQmlEngine, backend: BackendProcess):
        super().__init__()
        self._app = app
        self._engine = engine
        self._backend = backend
        self._net = QNetworkAccessManager(self)

        self._slots: dict[str, _DisplaySlot] = {}
        self._assignment: Assignment | None = None
        self._entries: list[ScreenEntry] = []
        self._displays_info: list[dict] = []

        self._telex = TelexBridge(self)
        self._admin = AdminClient(self)
        self._management: QQuickWindow | None = None
        self._management_mode = ""  # "" | "fullscreen" | "window"

        self._identifying = False
        self._identify_timer = QTimer(self)
        self._identify_timer.setSingleShot(True)
        self._identify_timer.timeout.connect(lambda: self._set_identifying(False))

        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(LAYOUT_SETTLE_MS)
        self._settle.timeout.connect(self.rebuild)

        self._targets: dict[str, _Target] = {}
        self._touch_warning = ""
        self._guard = QTimer(self)
        self._guard.setInterval(GUARD_INTERVAL_MS)
        self._guard.timeout.connect(lambda: self._check_placement(report=False))

        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._on_screens_changed)
        app.primaryScreenChanged.connect(self._on_screens_changed)
        backend.ready.connect(self._post_layout)
        for screen in app.screens():
            self._watch_screen(screen)

        self._display_component = self._load("DisplayWindow.qml")
        self._management_component = self._load("ManagementWindow.qml")

    def _load(self, name: str) -> QQmlComponent:
        component = QQmlComponent(self._engine, QUrl.fromLocalFile(str(QML_DIR / name)))
        if component.isError():
            raise RuntimeError(f"Lỗi QML {name}: " + "; ".join(e.toString() for e in component.errors()))
        return component

    def _create(self, component: QQmlComponent, props: dict) -> QQuickWindow:
        obj = component.createWithInitialProperties(props, self._engine.rootContext())
        if obj is None:
            raise RuntimeError("Không tạo được cửa sổ: " + "; ".join(e.toString() for e in component.errors()))
        return obj

    # ---------- vòng đời ----------

    def start(self) -> None:
        self._admin.start()
        self.rebuild()
        self._guard.start()

    def shutdown(self) -> None:
        self._settle.stop()
        self._guard.stop()
        self._targets.clear()
        for slot in self._slots.values():
            slot.close()
        self._slots.clear()
        self._close_management()
        self._admin.close()

    # ---------- xếp cửa sổ ----------

    def _on_screens_changed(self, *_args) -> None:
        logger.info("Windows báo thay đổi màn — chờ %s ms cho ổn định rồi xếp lại", LAYOUT_SETTLE_MS)
        self._settle.start()

    def _on_screen_added(self, screen: QScreen) -> None:
        self._watch_screen(screen)
        self._on_screens_changed()

    def _watch_screen(self, screen: QScreen) -> None:
        # Đổi độ phân giải / scale / vị trí trong Windows Settings cũng phải xếp lại.
        # Nối đúng 1 lần cho mỗi màn (lúc khởi động hoặc lúc màn được cắm vào).
        screen.geometryChanged.connect(self._on_screens_changed)
        screen.logicalDotsPerInchChanged.connect(self._on_screens_changed)

    @Slot()
    def rebuild(self, force: bool = False) -> None:
        # Lỗi ở đây mà để lọt thì các màn đứng hình ở bố cục cũ — ghi log rồi thử lại sau.
        try:
            self._rebuild(force)
        except Exception:
            logger.exception("Xếp cửa sổ thất bại — thử lại sau %s ms", LAYOUT_SETTLE_MS)
            self._settle.start()

    def _rebuild(self, force: bool) -> None:
        self._targets.clear()
        entries = read_screens(self._app)
        assignment = assign([e.monitor for e in entries])
        by_key = {e.monitor.key: e for e in entries}
        wanted = {d.monitor.key: d.role for d in assignment.displays}

        for key, slot in list(self._slots.items()):
            if force or wanted.get(key) != slot.role:
                slot.close()
                del self._slots[key]

        for display in assignment.displays:
            entry = by_key[display.monitor.key]
            slot = self._slots.get(entry.monitor.key)
            created = slot is None
            if created:
                slot = self._create_display(display.role)
                self._slots[entry.monitor.key] = slot
            info = {**entry.describe(), "role": display.role, "wall_index": display.wall_index,
                    "role_name": ROLE_NAMES[display.role]}
            slot.window.setProperty("info", info)
            _place_fullscreen(slot.window, entry.screen)
            if created:
                win32.disable_touch_feedback(int(slot.window.winId()))
            # Màn phụ: nổi trên taskbar của màn đó (taskbar hay đè lên cửa sổ toàn màn hình không
            # được chọn). Màn chính thì không — để người vận hành còn mở được Task Manager.
            self._targets[entry.monitor.key] = _Target(
                f"Màn {display.role}", slot.window, entry, topmost=not entry.monitor.primary)

        management_entry = by_key.get(assignment.management.key) if assignment.management else None
        if management_entry is not None:
            if self._management_mode != "fullscreen":
                self._close_management()
                self._open_management("fullscreen")
            _place_fullscreen(self._management, management_entry.screen)
            self._targets["management"] = _Target("Màn quản lý", self._management, management_entry,
                                                   topmost=False, giu_tren_cung=False)
        elif self._management_mode == "fullscreen":
            self._close_management()

        self._entries = entries
        self._assignment = assignment
        self._displays_info = [
            {**by_key[d.monitor.key].describe(), "role": d.role, "wall_index": d.wall_index}
            for d in assignment.displays
        ]
        self.displaysChanged.emit()
        self.managementChanged.emit()

        logger.info(
            "Bố cục: %s màn | quản lý: %s | hiển thị: %s | không dùng: %s",
            len(entries),
            assignment.management.key if assignment.management else "không",
            ", ".join(f"{d.monitor.key}→màn {d.role}{' (cảm ứng)' if d.monitor.touch else ''}"
                      f" [{d.monitor.width}x{d.monitor.height}, {by_key[d.monitor.key].gpu or '?'}]"
                      for d in assignment.displays),
            ", ".join(m.key for m in assignment.unused) or "không",
        )
        warning = touch_problem(touch_devices(), entries) or ""
        if warning:
            logger.warning("Cảm ứng: %s", warning)
        if warning != self._touch_warning:
            self._touch_warning = warning
            self.touchWarningChanged.emit()
        self._post_layout()
        QTimer.singleShot(PLACEMENT_CHECKS_MS[0], lambda: self._check_placement(report=False))
        QTimer.singleShot(PLACEMENT_CHECKS_MS[1], lambda: self._check_placement(report=True))

    # ---------- kiểm vị trí thật ----------

    def _check_placement(self, report: bool) -> None:
        try:
            self._check_placement_now(report)
        except Exception:
            logger.exception("Kiểm vị trí cửa sổ thất bại")

    def _check_placement_now(self, report: bool) -> None:
        for target in list(self._targets.values()):
            window, entry = target.window, target.entry
            hwnd = int(window.winId())
            if win32.is_minimized(hwnd) or window.visibility() != QWindow.Visibility.FullScreen:
                logger.warning("%s bị thu nhỏ / thoát toàn màn hình — mở lại", target.label)
                _place_fullscreen(window, entry.screen, force=True)
            actual = win32.window_rect(hwnd)
            if actual is None:  # không phải Windows
                continue
            on_monitor = win32.monitor_of_window(hwnd)
            ok = win32.rect_matches(actual, entry.rect) and (not entry.handle or on_monitor == entry.handle)
            if ok:
                if target.misses:
                    logger.info("%s đã khớp lại %s", target.label, entry.monitor.key)
                elif report:
                    logger.info("%s khớp %s: cửa sổ %s = màn %s (scale %s%%)", target.label,
                                entry.monitor.key, actual, entry.rect, entry.scale_percent)
                target.misses = 0
            else:
                target.misses += 1
                logger.warning("%s LỆCH %s: cửa sổ %s, màn %s (lần %s)", target.label,
                               entry.monitor.key, actual, entry.rect, target.misses)
                if target.misses == 1:
                    _place_fullscreen(window, entry.screen, force=True)
                else:
                    win32.force_rect(hwnd, entry.rect, target.topmost)
            if target.topmost:
                win32.set_topmost(hwnd, True)
            elif target.keep_visible:
                # Màn hiển thị nằm trên màn chính: không đặt "luôn trên cùng" (để còn mở được
                # Task Manager khi cần), nhưng vẫn phải đẩy lên trên các cửa sổ thường — cửa sổ
                # hiển thị không nhận kích hoạt nên chương trình nào mở ra cũng nằm đè lên nó.
                win32.raise_window(hwnd)
        # Bảng điều khiển dạng nổi phải nằm trên các màn vừa được đẩy lên trên cùng.
        if self._management_mode == "window" and self._management is not None:
            win32.set_topmost(int(self._management.winId()), True)

    def _create_display(self, role: int) -> _DisplaySlot:
        client = ScreenClient(role)
        sync = StandbySync()
        window = self._create(self._display_component, {
            "client": client, "sync": sync, "manager": self, "role": role,
        })
        if role in TOUCH_ROLES:
            # Bộ lọc thuộc cửa sổ (parent) nên sống cùng cửa sổ, không cần giữ thêm tham chiếu.
            window.installEventFilter(_WakeOnPress(client, window))
        client.start()
        return _DisplaySlot(role, window, client, sync)

    # ---------- màn quản lý ----------

    def _open_management(self, mode: str) -> None:
        self._management = self._create(self._management_component, {
            "admin": self._admin, "manager": self, "windowed": mode == "window",
        })
        self._management_mode = mode
        # Không dùng tín hiệu `closing`: PySide không chuyển được tham số QQuickCloseEvent.
        self._management.visibleChanged.connect(self._on_management_visible)

    def _close_management(self) -> None:
        window, self._management, self._management_mode = self._management, None, ""
        if window is not None:
            window.visibleChanged.disconnect(self._on_management_visible)
            window.close()
            window.deleteLater()

    def _on_management_visible(self, visible: bool) -> None:
        # Chỉ cửa sổ quản lý dạng nổi mới đóng được bằng nút X.
        if not visible and self._management_mode == "window":
            QTimer.singleShot(0, self._close_management)
            QTimer.singleShot(0, self.managementChanged.emit)

    @Slot()
    def toggleManagement(self) -> None:
        if self._management_mode == "fullscreen":
            self._management.requestActivate()
            return
        if self._management_mode == "window":
            self._close_management()
            self.managementChanged.emit()
            return
        self._open_management("window")
        screen = self._app.primaryScreen()
        area = screen.availableGeometry()
        w, h = WINDOWED_MANAGEMENT_SIZE
        w, h = min(w, area.width()), min(h, area.height())
        self._management.setScreen(screen)
        self._management.setGeometry(QRect(area.x() + (area.width() - w) // 2,
                                           area.y() + (area.height() - h) // 2, w, h))
        self._management.show()
        self._management.requestActivate()
        self.managementChanged.emit()

    # ---------- lệnh từ giao diện ----------

    @Slot()
    def identify(self) -> None:
        self._set_identifying(True)
        self._identify_timer.start(IDENTIFY_SECONDS * 1000)

    def _set_identifying(self, value: bool) -> None:
        if value != self._identifying:
            self._identifying = value
            self.identifyChanged.emit()

    @Slot()
    def resetSystem(self) -> None:
        logger.warning("Reset hệ thống từ màn quản lý")
        self._admin.command("reset")
        # Tạo lại toàn bộ cửa sổ hiển thị — gỡ mọi trạng thái kẹt phía giao diện (nếu có).
        QTimer.singleShot(300, lambda: self.rebuild(force=True))

    @Slot()
    def quit(self) -> None:
        logger.info("Người vận hành thoát app")
        self._app.quit()

    # ---------- báo bố cục cho backend ----------

    def _post_layout(self) -> None:
        if self._assignment is None or not self._assignment.displays or not self._backend.is_ready:
            return
        body = json.dumps(self._assignment.as_layout_request()).encode("utf-8")
        request = QNetworkRequest(QUrl(f"{BACKEND_URL}/api/layout"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        reply = self._net.post(request, QByteArray(body))
        reply.finished.connect(lambda: self._on_layout_posted(reply))

    def _on_layout_posted(self, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.error("Gửi bố cục màn cho backend thất bại: %s %s",
                         reply.errorString(), bytes(reply.readAll()).decode("utf-8", "replace"))
        reply.deleteLater()

    # ---------- thuộc tính cho QML ----------

    identifying = Property(bool, lambda self: self._identifying, notify=identifyChanged)
    identifySeconds = Property(int, lambda self: IDENTIFY_SECONDS, constant=True)
    displays = Property("QVariantList", lambda self: self._displays_info, notify=displaysChanged)
    monitorCount = Property(int, lambda self: len(self._entries), notify=displaysChanged)
    unusedCount = Property(int, lambda self: len(self._assignment.unused) if self._assignment else 0,
                           notify=displaysChanged)
    managementMode = Property(str, lambda self: self._management_mode, notify=managementChanged)
    hospitalName = Property(str, lambda self: HOSPITAL_NAME, constant=True)
    touchWarning = Property(str, lambda self: self._touch_warning, notify=touchWarningChanged)
    telex = Property(QObject, lambda self: self._telex, constant=True)
