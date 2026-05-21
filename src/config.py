"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\\TrayForge\\"""

import json
import os
from logger import get_main_logger


def get_data_dir() -> str:
    """Get or create the data directory under LOCALAPPDATA."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    data_dir = os.path.join(local_appdata, "TrayForge")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_config_path() -> str:
    return os.path.join(get_data_dir(), "config.json")


def get_default_config() -> dict:
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
                "webui_pattern": "Starting WebUI at (https?:\\/\\/\\S+)",
                "delete_before_start": ["astrbot.lock"],
            },
        ],
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }


def _migrate_old_config(old: dict) -> dict:
    """Convert old {napcat:{...}, astrbot:{...}} format to processes[] array."""
    logger = get_main_logger()
    logger.info("Migrating old config format to new processes[] schema")
    processes = []
    for key in ("napcat", "astrbot"):
        if key in old:
            proc = old[key]
            processes.append(
                {
                    "name": "NapCat" if key == "napcat" else "AstrBot",
                    "cwd": proc.get("cwd", ""),
                    "cmd": proc.get("cmd", ""),
                    "encoding": proc.get("encoding", "utf-8"),
                    "singleton": True,
                    "autostart": old.get("autostart", False),
                    "webui_pattern": (
                        "\\[WebUi\\] WebUi User Panel Url: (https?:\\/\\/\\S+)"
                        if key == "napcat"
                        else "Starting WebUI at (https?:\\/\\/\\S+)"
                    ),
                    "delete_before_start": ["astrbot.lock"] if key == "astrbot" else [],
                }
            )
    return {
        "processes": processes,
        "output_refresh_ms": old.get("output_refresh_ms", 500),
        "poll_interval_ms": old.get("poll_interval_ms", 2000),
        "autostart": old.get("autostart", False),
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
        if "processes" not in config:
            config = _migrate_old_config(config)
            save_config(config)
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
