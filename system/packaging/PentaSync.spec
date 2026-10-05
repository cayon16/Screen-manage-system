# -*- mode: python ; coding: utf-8 -*-
# Đóng gói PentaSync thành 1 thư mục chạy được không cần cài Python.
# Đừng gọi trực tiếp — chạy packaging/build.py (nó còn chép nội dung, video, lát video cạnh exe).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SYSTEM = Path(SPECPATH).parent

# Những phần Qt app không dùng tới — bỏ đi cho nhẹ (riêng QtWebEngine đã ~200 MB).
UNUSED_QT = (
    "QtWebEngine", "WebEngine", "Qt3D", "Qt63D", "QtQuick3D", "Qt6Quick3D", "QtCharts", "Qt6Charts",
    "QtDataVisualization", "Qt6DataVisualization", "QtGraphs", "Qt6Graphs", "QtLocation",
    "Qt6Location", "QtPositioning", "Qt6Positioning", "QtSensors", "Qt6Sensors", "QtTest",
    "Qt6Test", "QtWebView", "Qt6WebView", "QtRemoteObjects", "Qt6RemoteObjects", "QtScxml",
    "Qt6Scxml", "QtStateMachine", "Qt6StateMachine", "QtTextToSpeech", "Qt6TextToSpeech",
    "QtVirtualKeyboard", "Qt6VirtualKeyboard", "QtPdf", "Qt6Pdf", "QtDesigner", "Qt6Designer",
    "QtSpatialAudio", "Qt6SpatialAudio", "QtHttpServer", "Qt6HttpServer", "Qt6Bluetooth",
    "QtBluetooth", "Qt6Nfc", "QtNfc", "Qt6SerialPort", "QtSerialPort", "QtQuick/Controls",
    "Qt6QuickControls2", "QtQuick/Dialogs", "Qt6QuickDialogs2", "QtQuick/NativeStyle",
    "QtQuick/Timeline", "Qt6QuickTimeline", "QtQuick/Particles", "Qt6QuickParticles",
    "QtQuick/Scene2D", "QtQuick/Scene3D", "Qt6ShaderTools", "opengl32sw.dll", "Qt6Help",
    "QtHelp", "translations",
)


def _unused(dest):
    dest = dest.replace("\\", "/")
    return any(name in dest for name in UNUSED_QT)


a = Analysis(
    [str(SYSTEM / "desktop" / "run.py")],
    pathex=[str(SYSTEM), str(SYSTEM / "backend")],
    datas=[
        (str(SYSTEM / "desktop" / "qml"), "desktop/qml"),
        (str(SYSTEM / "desktop" / "fonts"), "desktop/fonts"),
        *collect_data_files("imageio_ffmpeg"),
    ],
    hiddenimports=[
        "desktop.main",
        "desktop.backend_entry",
        "app.main",
        "app.superdoc.gemini_provider",
        *collect_submodules("uvicorn"),
    ],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtWebEngineQuick", "PySide6.QtWidgets"],
    noarchive=False,
)
a.binaries = [entry for entry in a.binaries if not _unused(entry[0])]
a.datas = [entry for entry in a.datas if not _unused(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PentaSync",
    console=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="PentaSync",
)
