"""Pytest configuration — add src/ to path."""

import sys
from pathlib import Path
import pytest

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from process_mgr import ProcessManager  # noqa: E402


@pytest.fixture
def pm():
    """ProcessManager with default config (NapCat, AstrBot)."""
    config = {
        "processes": [
            {
                "name": "NapCat",
                "cwd": "",
                "cmd": "NapCatWinBootMain.exe",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "cleanup_cwd": False,
                "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?:\\/\\/\\S+)",
                "delete_before_start": [],
            },
            {
                "name": "AstrBot",
                "cwd": "",
                "cmd": "astrbot",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "cleanup_cwd": False,
                "webui_pattern": None,
                "delete_before_start": [],
            },
        ],
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }
    return ProcessManager(config)
