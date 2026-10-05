import logging
from logging.handlers import RotatingFileHandler

from app.config import LOG_FILE, MAX_LOG_SIZE

_configured = False


def get_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger("pentasync")
    if not _configured:
        logger.setLevel(logging.INFO)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        _configured = True
    return logger
