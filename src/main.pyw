"""AIRobotUI - tray controller for managed processes."""

import sys
import os
import time
import webbrowser

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

        tkinter.messagebox.showwarning("AIRobotUI", "AIRobotUI is already running.")
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

    # Set initial tabs
    window.set_processes(pm.process_names())

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
                window.set_processes(pm.process_names())
                logger.info("Config updated at runtime")
        finally:
            _settings_open = False

    tray.set_config_callback(open_settings)

    # --- Main event tick ---
    _last_poll = 0
    _last_output = 0
    _buffers: dict[str, list[str]] = {}

    def _tick() -> None:
        nonlocal _last_poll, _last_output

        # 1. Consume pending tray action
        action = tray.consume_action()
        if action:
            logger.info("Action: %s", action)
            if action == "startall":
                pm.start_all()
            elif action == "stopall":
                pm.stop_all()
            elif ":" in action:
                cmd, _, name = action.partition(":")
                if cmd == "start":
                    pm.start(name)
                elif cmd == "stop":
                    pm.stop(name)
                elif cmd == "webui":
                    url = pm.get_webui_url(name)
                    if url:
                        try:
                            ok = webbrowser.open(url)
                            if not ok:
                                logger.warning("Failed to open %s WebUI: %s", name, url)
                        except Exception:
                            logger.warning(
                                "Failed to open %s WebUI: %s",
                                name,
                                url,
                                exc_info=True,
                            )
                    else:
                        pm._system_msg(name, f"{name} WebUI URL not detected yet")

        # 2. Drain output queues to per-process buffers
        for name in pm.process_names():
            buf = _buffers.setdefault(name, [])
            buf.extend(pm.drain(name))

        # 3. Flush buffers to window at configured interval (batch insert to prevent UI freeze)
        now = time.monotonic() * 1000
        interval = config.get("output_refresh_ms", 500)
        if now - _last_output >= interval:
            _last_output = now
            for name in pm.process_names():
                buf = _buffers.get(name)
                if buf:
                    chunk = "\n".join(buf)
                    window.append_output(name, chunk)
                    buf.clear()

        # 4. Periodic crash poll
        if now - _last_poll >= config.get("poll_interval_ms", 2000):
            _last_poll = now
            pm.poll_crashes()

        # 5. Exit check
        if tray._exit_requested:
            logger.info("Exit: hiding window, shutting down...")
            # Flush remaining output before exit
            for name in pm.process_names():
                buf = _buffers.get(name)
                if buf:
                    window.append_output(name, "\n".join(buf))
                    buf.clear()
            pm.shutdown()
            window.hide()
            window.root.quit()
            return

        window.root.after(100, _tick)

    # --- Setup ---
    if is_first:
        window.root.after(300, open_settings)

    tray.run()

    # Autostart processes marked for auto-start
    for proc in config.get("processes", []):
        if proc.get("autostart"):
            name = proc["name"]
            logger.info("Autostart: %s", name)
            window.root.after(500, lambda n=name: pm.start(n))

    window.root.after(100, _tick)

    logger.info("Entering tkinter main loop")
    window.root.mainloop()

    # --- Cleanup ---
    logger.info("Mainloop exited, cleaning up...")
    try:
        window.destroy()
    except Exception:
        pass
    import logging

    for lg_name in ("airobotui.main",):
        lg = logging.getLogger(lg_name)
        for h in lg.handlers:
            h.flush()
            h.close()
    logger.info("AIRobotUI exited")
    os._exit(0)


if __name__ == "__main__":
    main()
