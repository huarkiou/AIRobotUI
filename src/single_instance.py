"""Single-instance enforcement via Windows named mutex."""

import sys
import ctypes


MUTEX_NAME = "Global\\AIRobotUI_SingleInstance"


def ensure_single_instance() -> bool:
    """Try to acquire named mutex. Returns True if we're the only instance."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True
