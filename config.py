"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\\AIRobotUI\\"""

import json
import os
from logger import get_main_logger


def get_data_dir() -> str:
    """Get or create the data directory under LOCALAPPDATA."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    data_dir = os.path.join(local_appdata, "AIRobotUI")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_config_path() -> str:
    return os.path.join(get_data_dir(), "config.json")


def get_default_config() -> dict:
    """Return default configuration."""
    import locale
    sys_enc = locale.getpreferredencoding() or "utf-8"
    return {
        "napcat": {
            "cwd": "D:\\Apps\\ai\\napcatqq\\NapCat.44498.Shell",
            "cmd": "NapCatWinBootMain.exe 2450085301",
            "encoding": "utf-8",
        },
        "astrbot": {
            "cwd": "D:\\Apps\\ai\\astrbot",
            "cmd": "astrbot run",
            "encoding": "utf-8",
        },
        "autostart": False,
    }


def load_config() -> dict | None:
    """Load config from file. Returns None if file does not exist."""
    logger = get_main_logger()
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        logger.info("Config file not found at %s", config_path)
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info("Config loaded from %s", config_path)
        return config
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load config: %s", e)
        return None


def save_config(config: dict) -> bool:
    """Save config to file. Returns True on success."""
    logger = get_main_logger()
    config_path = _get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Config saved to %s", config_path)
        return True
    except IOError as e:
        logger.error("Failed to save config: %s", e)
        return False
