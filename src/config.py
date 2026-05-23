"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\\TrayForge\\"""

import json
import os
from logger import get_main_logger
from trayforge_types import AppConfig


def get_data_dir() -> str:
    """Get or create the data directory. Respects TRAYFORGE_DATA_DIR env var."""
    custom = os.environ.get("TRAYFORGE_DATA_DIR")
    if custom:
        os.makedirs(custom, exist_ok=True)
        return custom
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    data_dir = os.path.join(local_appdata, "TrayForge")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_config_path() -> str:
    return os.path.join(get_data_dir(), "config.json")


def get_default_config() -> AppConfig:
    """Return default configuration with processes array."""
    return {
        "processes": [
            {
                "name": "NapCat",
                "cwd": "",
                "cmd": "NapCatWinBootMain.exe <your-qq>",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "cleanup_cwd": True,
                "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?:\\/\\/\\S+)",
                "delete_before_start": [],
            },
            {
                "name": "AstrBot",
                "cwd": "",
                "cmd": "astrbot run",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "cleanup_cwd": True,
                "webui_pattern": "Starting WebUI at (https?:\\/\\/\\S+)",
                "delete_before_start": ["astrbot.lock"],
            },
        ],
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }


def load_config() -> AppConfig | None:
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


def save_config(config: AppConfig) -> bool:
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
