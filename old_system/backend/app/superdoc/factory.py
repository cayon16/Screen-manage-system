from __future__ import annotations

from app.config import SUPERDOC_PROVIDER
from app.logging_setup import get_logger
from app.superdoc.base import SuperdocProvider
from app.superdoc.mock_provider import MockSuperdocProvider

logger = get_logger()


def build_provider(name: str = SUPERDOC_PROVIDER) -> SuperdocProvider:
    """Chon provider theo cau hinh. Neu provider that khong khoi tao duoc (thieu API key,
    thieu thu vien...) thi lui ve mock va ghi log — man hinh hanh lang benh vien khong duoc
    phep chet chi vi thieu 1 bien moi truong."""
    if name == "gemini":
        try:
            from app.superdoc.gemini_provider import GeminiSuperdocProvider

            provider = GeminiSuperdocProvider()
            logger.info("Superdoc provider: gemini")
            return provider
        except Exception:
            logger.exception("Khong khoi tao duoc provider gemini — lui ve mock")
            return MockSuperdocProvider()

    if name != "mock":
        logger.warning("SUPERDOC_PROVIDER=%r khong nhan dien duoc — dung mock", name)
    else:
        logger.info("Superdoc provider: mock")
    return MockSuperdocProvider()
