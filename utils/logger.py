import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
LOG_FILE = "logs/app.log"


def resolve_level(level) -> int:
    if isinstance(level, int):
        return level

    normalized = str(level or "INFO").strip().upper()
    return getattr(logging, normalized, logging.INFO)


def setup_logger(name="app", level="INFO"):
    """Create or update the shared SparkFlow logger."""
    resolved_level = resolve_level(level)
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(LOG_FORMAT)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # The same logger may be initialized before config is loaded. Keep handler
    # levels synchronized with the latest requested LOG_LEVEL.
    for handler in logger.handlers:
        handler.setLevel(resolved_level)

    return logger


if __name__ == "__main__":
    logger = setup_logger(level="DEBUG")
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
