"""AIRobotUI - tray controller for NapCat QQ and AstrBot."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from single_instance import ensure_single_instance
from logger import get_main_logger
from config import load_config, get_default_config, save_config
from process_mgr import ProcessManager
from main_window import MainWindow
from config_ui import ConfigDialog
from tray_ui import TrayUI


def main() -> None:
    logger = get_main_logger()

    # --- Single instance ---
    if not ensure_single_instance():
        logger.warning("Another instance is already running, exiting")
        import tkinter.messagebox
        tkinter.messagebox.showwarning(
            "AIRobotUI", "AIRobotUI is already running."
        )
        return

    logger.info("=" * 40)
    logger.info("AIRobotUI starting...")

    window = MainWindow()

    is_first = load_config() is None
    config = get_default_config() if is_first else load_config()
    if is_first:
        save_config(config)

    pm = ProcessManager(config)
    tray = TrayUI(pm, window, config)

    _settings_open = False

    def open_settings() -> None:
        nonlocal _settings_open
        if _settings_open:
            return
        _settings_open = True
        logger.info("Opening settings dialog")
        try:
            dlg = ConfigDialog(window.root)
            result = dlg.get_result()
            if result is not None:
                pm.update_config(result)
                logger.info("Config updated at runtime")
        finally:
            _settings_open = False

    tray.set_config_callback(open_settings)

    # --- Main event tick (runs on tkinter main thread) ---
    POLL_INTERVAL_MS = 2000
    _last_poll = 0

    def _tick() -> None:
        nonlocal _last_poll

        # 1. Consume pending tray action
        action = tray.consume_action()
        if action:
            logger.info("Action: %s", action)
            if action == "start:all":
                pm.start_all()
            elif action == "stop:all":
                pm.stop_all()
            elif action == "start:napcat":
                pm.start_napcat()
            elif action == "stop:napcat":
                pm.stop_napcat()
            elif action == "start:astrbot":
                pm.start_astrbot()
            elif action == "stop:astrbot":
                pm.stop_astrbot()

        # 2. Drain output to window
        for line in pm.drain_napcat():
            window.append_output("NapCat", line)
        for line in pm.drain_astrbot():
            window.append_output("AstrBot", line)

        # 3. Periodic crash poll
        now = time.monotonic() * 1000
        if now - _last_poll >= POLL_INTERVAL_MS:
            _last_poll = now
            pm.poll_crashes()

        # 4. Exit check
        if tray._exit_requested:
            logger.info("Exit: hiding window, shutting down...")
            window.hide()
            pm.shutdown()
            window.root.quit()
            return

        window.root.after(100, _tick)

    # --- Setup ---
    if is_first:
        window.root.after(300, open_settings)

    tray.run()
    window.root.after(100, _tick)

    logger.info("Entering tkinter main loop")
    window.root.mainloop()

    # --- Cleanup ---
    logger.info("Mainloop exited, cleaning up...")
    try:
        window.destroy()
    except Exception:
        pass
    time.sleep(0.5)
    logger.info("AIRobotUI exited")


if __name__ == "__main__":
    main()
