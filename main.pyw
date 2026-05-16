"""AIRobotUI - Windows system tray controller for NapCat QQ and AstrBot."""

import sys
import os

# Ensure script directory is on path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import get_main_logger
from config import load_config, get_default_config, save_config
from process_mgr import ProcessManager
from main_window import MainWindow
from config_ui import ConfigDialog
from tray_ui import TrayUI


def main() -> None:
    logger = get_main_logger()
    logger.info("=" * 40)
    logger.info("AIRobotUI starting...")

    # Step 1: Create main window (needed for config dialog parent)
    window = MainWindow()

    # Step 2: Load or create config
    is_first = load_config() is None
    if is_first:
        logger.info("No config found, using defaults")
        config = get_default_config()
        save_config(config)
    else:
        config = load_config()

    # Step 3: Initialize process manager
    pm = ProcessManager(config)

    # Step 4: Wire output to main window
    pm.on_output(window.append_output)

    # Step 5: Create tray UI
    tray = TrayUI(pm, window, config)

    # Step 6: Settings callback (thread-safe via root.after, guarded against re-entry)
    _settings_open = False

    def open_settings() -> None:
        nonlocal _settings_open
        if _settings_open:
            logger.info("Settings dialog already open, ignoring")
            return
        _settings_open = True
        logger.info("Opening settings dialog")
        try:
            dialog = ConfigDialog(window.root)
            result = dialog.get_result()
            if result is not None:
                pm.update_config(result)
                logger.info("Config updated at runtime")
        finally:
            _settings_open = False

    tray.set_config_callback(open_settings)

    # Step 7: First-run: show config dialog after mainloop starts
    if is_first:
        logger.info("Scheduling first-run settings dialog...")
        window.root.after(300, open_settings)

    # Step 8: Start tray in background thread (non-blocking)
    logger.info("Starting tray in background thread...")
    tray.run()

    # Step 9: Run tkinter mainloop in main thread
    logger.info("Entering tkinter main loop")
    window.root.mainloop()

    logger.info("AIRobotUI exited")


if __name__ == "__main__":
    main()
