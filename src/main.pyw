"""TrayForge - tray controller for managed processes."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from single_instance import ensure_single_instance
from logger import get_main_logger
from config import load_config, get_default_config, save_config
from process_mgr import ProcessManager
from main_window import MainWindow
from tray_ui import TrayUI
from app_controller import AppController


def main() -> None:
    logger = get_main_logger()

    if not ensure_single_instance():
        import tkinter.messagebox

        tkinter.messagebox.showwarning("TrayForge", "TrayForge is already running.")
        return

    logger.info("=" * 40)
    logger.info("TrayForge starting...")

    window = MainWindow()

    is_first = load_config() is None
    config = get_default_config() if is_first else load_config()
    if is_first:
        save_config(config)

    pm = ProcessManager(config)
    tray = TrayUI(pm, window, config)
    window.set_processes(pm.process_names())

    app = AppController(config, pm, window, tray)
    app.start(is_first)


if __name__ == "__main__":
    main()
