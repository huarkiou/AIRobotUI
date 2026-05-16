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
    config = load_config()
    if config is None:
        logger.info("No config found, saving defaults...")
        config = get_default_config()
        save_config(config)

    # Step 3: Show config dialog on first run (blocking)
    if config is None or _is_first_run():
        logger.info("Showing first-run settings dialog...")
        dialog = ConfigDialog(window.root)
        result = dialog.get_result()
        if result is not None:
            config = result

    # Step 4: Initialize process manager
    pm = ProcessManager(config)

    # Step 5: Wire output to main window
    pm.on_output(window.append_output)

    # Step 6: Create tray UI
    tray = TrayUI(pm, window, config)

    # Step 7: Settings callback
    def open_settings() -> None:
        logger.info("Opening settings dialog")
        dialog = ConfigDialog(window.root)
        result = dialog.get_result()
        if result is not None:
            pm.update_config(result)
            logger.info("Config updated at runtime")

    tray.set_config_callback(open_settings)

    # Step 8: Start tray (blocking)
    logger.info("Entering tray event loop")
    tray.run()

    logger.info("AIRobotUI exited")


def _is_first_run() -> bool:
    """Check if this is the first run (based on config existence)."""
    from config import load_config
    return load_config() is None


if __name__ == "__main__":
    main()
