import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_LEVEL_ENV_VAR = "LOG_LEVEL"
LOG_DIR_ENV_VAR = "HEART_LOG_DIR"
DEFAULT_LOG_SUBDIR = Path(".heart") / "logs"
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MiB
BACKUP_COUNT = 5


def _resolve_log_directory() -> Path:
    """Return the directory where log files should be written."""

    log_dir = os.getenv(LOG_DIR_ENV_VAR)
    if log_dir:
        path = Path(log_dir).expanduser()
    else:
        path = Path.home() / DEFAULT_LOG_SUBDIR

    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_logger_name(name: str) -> str:
    """Convert a logger name to a filesystem-friendly filename."""

    sanitized = name.replace("/", "_").replace(os.sep, "_")
    sanitized = sanitized.replace("..", ".")
    return sanitized.replace(".", "_") or "root"


def _configure_logger(logger: logging.Logger, log_level: str) -> None:
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)

    if logger.handlers:
        # Logger already configured elsewhere; respect existing handlers.
        return

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        _resolve_log_directory() / f"{_sanitize_logger_name(logger.name)}.log",
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with stream and rolling file handlers."""

    log_level = os.getenv(LOG_LEVEL_ENV_VAR, "INFO").upper()
    logger = logging.getLogger(name)
    _configure_logger(logger, log_level)
    return logger
