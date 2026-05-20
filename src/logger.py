"""Logging module for AIRobotUI - writes to %%LOCALAPPDATA%%\\AIRobotUI\\logs\\"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler


def _get_log_dir() -> str:
    """Get or create the log directory under LOCALAPPDATA."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(local_appdata, "AIRobotUI", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _create_logger(name: str, filename: str) -> logging.Logger:
    """Create a logger with rotating file handler."""
    log_dir = _get_log_dir()
    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=1 * 1024 * 1024,  # 1 MB
            backupCount=3,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_process_logger(name: str) -> logging.Logger:
    """Get a logger for a managed process. Name is sanitized to a safe filename."""
    safe = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff-]", "_", name).strip("_") or "process"
    return _create_logger(f"airobotui.process.{safe}", f"{safe}.log")


# Module-level singletons
_main_logger = None


def get_main_logger() -> logging.Logger:
    global _main_logger
    if _main_logger is None:
        _main_logger = _create_logger("airobotui.main", "airobotui.log")
    return _main_logger


def get_napcat_logger() -> logging.Logger:
    return get_process_logger("NapCat")


def get_astrbot_logger() -> logging.Logger:
    return get_process_logger("AstrBot")
