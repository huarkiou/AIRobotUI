"""Windows autostart management via registry."""

import sys
import os
import winreg
from logger import get_main_logger

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "TrayForge"


def _get_exe_path() -> str:
    """Get the path to use for autostart entry."""
    if getattr(sys, "frozen", False):
        # Running as compiled EXE
        return sys.executable
    else:
        # Running from source - use Python with script path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(script_dir, "main.pyw")
        return f'"{sys.executable}" "{main_script}"'


def is_autostart_enabled() -> bool:
    """Check if autostart registry entry exists."""
    logger = get_main_logger()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, REG_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.error("Failed to read autostart registry: %s", e)
        return False


def enable_autostart() -> bool:
    """Create autostart registry entry. Returns True on success."""
    logger = get_main_logger()
    exe_path = _get_exe_path()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, exe_path)
        logger.info("Autostart enabled: %s", exe_path)
        return True
    except OSError as e:
        logger.error("Failed to enable autostart: %s", e)
        return False


def disable_autostart() -> bool:
    """Remove autostart registry entry. Returns True on success."""
    logger = get_main_logger()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, REG_VALUE_NAME)
        logger.info("Autostart disabled")
        return True
    except FileNotFoundError:
        return True  # Already not present
    except OSError as e:
        logger.error("Failed to disable autostart: %s", e)
        return False
