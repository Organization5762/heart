import logging
import os


def get_logger(name: str) -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level))
    logger = logging.getLogger(name)
    return logger
