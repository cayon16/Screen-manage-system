import pytest
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """Đối tượng Qt (QTimer, QWebSocket) cần có 1 QCoreApplication — không cần mở cửa sổ."""
    return QCoreApplication.instance() or QCoreApplication([])
