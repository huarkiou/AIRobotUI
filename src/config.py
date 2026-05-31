"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\\TrayForge\\"""

import json
import os
import shutil
from datetime import datetime
from logger import get_main_logger
from trayforge_types import AppConfig

BACKUP_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


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
    """Save config to file, with backup. Returns True on success."""
    logger = get_main_logger()
    config_path = _get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Backup existing config before overwriting
        _backup_config(config_path, logger)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Config saved to %s", config_path)
        return True
    except IOError as e:
        logger.error("Failed to save config: %s", e)
        return False


def _backup_config(config_path: str, logger) -> None:
    """Copy existing config to backups/ with timestamp, prune if > BACKUP_MAX_BYTES."""
    if not os.path.exists(config_path):
        return

    backup_dir = os.path.join(os.path.dirname(config_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    now = datetime.now()
    ts = now.strftime("%Y-%m-%d-%H%M%S") + f"-{now.microsecond // 1000:03d}"
    backup_name = f"config.{ts}.json"
    backup_path = os.path.join(backup_dir, backup_name)

    try:
        shutil.copy2(config_path, backup_path)
        logger.info("Config backup: %s", backup_name)
    except IOError as e:
        logger.warning("Failed to create backup: %s", e)
        return

    _prune_backups(backup_dir, logger)


def _prune_backups(backup_dir: str, logger) -> None:
    """Remove oldest backup files until total size <= BACKUP_MAX_BYTES."""
    files = []
    try:
        for name in os.listdir(backup_dir):
            path = os.path.join(backup_dir, name)
            if os.path.isfile(path) and name.startswith("config.") and name.endswith(".json"):
                files.append((path, os.path.getsize(path)))
    except OSError:
        return

    files.sort(key=lambda x: x[0])  # sort by path (timestamp in name = chronological)
    total = sum(sz for _, sz in files)

    while total > BACKUP_MAX_BYTES and files:
        oldest_path, oldest_sz = files.pop(0)
        try:
            os.remove(oldest_path)
            total -= oldest_sz
            logger.debug("Pruned old backup: %s", os.path.basename(oldest_path))
        except OSError:
            pass
