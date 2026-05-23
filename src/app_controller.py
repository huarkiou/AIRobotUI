"""AppController — orchestrates process_mgr, tray_ui, main_window lifecycle."""

import time
import webbrowser
import logging
import os
import threading
from http_server import create_server


class AppController:
    """Central orchestrator for the application event loop and lifecycle."""

    def __init__(self, config, process_mgr, main_window, tray_ui) -> None:
        self._config = config
        self._pm = process_mgr
        self._window = main_window
        self._tray = tray_ui

        self._buffers: dict[str, list[str]] = {}
        self._last_poll = 0.0
        self._last_output = 0.0
        self._settings_dialog = None
        self._settings_open = False
        self._http_server = None

    def _reload_config(self) -> bool:
        """Reload config from disk. Returns True on success."""
        from logger import get_main_logger
        from config import load_config

        logger = get_main_logger()
        config = load_config()
        if config:
            self._config = config
            self._pm.update_config(config)
            self._window.set_processes(self._pm.process_names())
            logger.info("Config reloaded from disk")
            return True
        else:
            logger.error("Failed to reload config — config file missing or corrupted")
            return False

    # --- Settings callback ---

    def _make_settings_callback(self) -> callable:
        from config_ui import ConfigDialog
        from logger import get_main_logger

        logger = get_main_logger()

        def open_settings() -> None:
            if self._settings_open:
                if self._settings_dialog is not None:
                    self._settings_dialog.lift_to_front()
                return
            self._settings_open = True
            logger.info("Opening settings dialog")
            try:
                dlg = ConfigDialog(self._window.root)
                self._settings_dialog = dlg
                result = dlg.get_result()
                if result is not None:
                    self._config = result
                    self._pm.update_config(result)
                    self._window.set_processes(self._pm.process_names())
                    logger.info("Config updated at runtime")
            finally:
                self._settings_open = False
                self._settings_dialog = None

        return open_settings

    # --- Action dispatch ---

    def _dispatch_action(self, action: str) -> None:
        from logger import get_main_logger

        logger = get_main_logger()
        logger.info("Action: %s", action)

        if action == "startall":
            self._pm.start_all()
        elif action == "stopall":
            self._pm.stop_all()
        elif action == "reload":
            self._reload_config()
        elif ":" in action:
            cmd, _, name = action.partition(":")
            if cmd == "start":
                self._pm.start(name)
            elif cmd == "stop":
                self._pm.stop(name)
            elif cmd == "restart":
                self._pm.restart(name)
            elif cmd == "webui":
                url = self._pm.get_webui_url(name)
                if url:
                    try:
                        ok = webbrowser.open(url)
                        if not ok:
                            logger.warning("Failed to open %s WebUI: %s", name, url)
                    except Exception:
                        logger.warning("Failed to open %s WebUI: %s", name, url, exc_info=True)
                else:
                    self._pm._system_msg(name, f"{name} WebUI URL not detected yet")

    # --- Main loop ---

    def _tick(self) -> None:
        # 1. Consume pending tray action
        action = self._tray.consume_action()
        if action:
            self._dispatch_action(action)

        # 2. Drain output queues to per-process buffers
        for name in self._pm.process_names():
            buf = self._buffers.setdefault(name, [])
            buf.extend(self._pm.drain(name))

        # 3. Flush buffers to window at configured interval
        now = time.monotonic() * 1000
        interval = self._config.get("output_refresh_ms", 500)
        if now - self._last_output >= interval:
            self._last_output = now
            for name in self._pm.process_names():
                buf = self._buffers.get(name)
                if buf:
                    chunk = "\n".join(buf)
                    self._window.append_output(name, chunk)
                    buf.clear()

        # 4. Periodic crash poll
        if now - self._last_poll >= self._config.get("poll_interval_ms", 2000):
            self._last_poll = now
            self._pm.poll_crashes()

        # 5. Exit check
        if self._tray._exit_requested:
            self._cleanup()
            return

        self._window.root.after(100, self._tick)

    # --- Lifecycle ---

    def start(self, is_first: bool) -> None:
        from logger import get_main_logger

        logger = get_main_logger()

        # Wire settings callback
        settings_cb = self._make_settings_callback()
        self._tray.set_config_callback(settings_cb)

        # First-run: open settings
        if is_first:
            self._window.root.after(300, settings_cb)

        # Start tray icon
        self._tray.run()

        # Autostart processes
        for proc in self._config.get("processes", []):
            if proc.get("autostart"):
                name = proc["name"]
                logger.info("Autostart: %s", name)
                self._window.root.after(500, lambda n=name: self._pm.start(n))

        # Start HTTP server for CLI control
        self._http_server = create_server(
            self._pm,
            self._window.root,
            self._reload_config,
        )
        port = self._http_server.server_address[1]
        threading.Thread(
            target=self._http_server.serve_forever,
            daemon=True,
            name="http-server",
        ).start()
        # Write port file for CLI discovery
        from config import get_data_dir

        port_file = os.path.join(get_data_dir(), "cli_port.txt")
        with open(port_file, "w") as f:
            f.write(str(port))
        logger.info("HTTP server listening on 127.0.0.1:%d", port)

        # Start event loop
        self._window.root.after(100, self._tick)

        logger.info("Entering tkinter main loop")
        self._window.root.mainloop()

        # After mainloop exits
        self._final_cleanup()

    def _cleanup(self) -> None:
        """Called when exit is requested during event loop."""
        from logger import get_main_logger

        logger = get_main_logger()
        logger.info("Exit: hiding window, shutting down...")
        # Shutdown HTTP server
        if self._http_server:
            logger.info("Stopping HTTP server")
            self._http_server.shutdown()
            from config import get_data_dir

            port_file = os.path.join(get_data_dir(), "cli_port.txt")
            try:
                os.remove(port_file)
            except OSError:
                pass
        # Flush remaining output
        for name in self._pm.process_names():
            buf = self._buffers.get(name)
            if buf:
                self._window.append_output(name, "\n".join(buf))
                buf.clear()
        self._pm.shutdown()
        self._window.hide()
        self._window.root.quit()

    def _final_cleanup(self) -> None:
        """Called after mainloop exits."""
        from logger import get_main_logger

        logger = get_main_logger()
        logger.info("Mainloop exited, cleaning up...")
        try:
            self._window.destroy()
        except Exception:
            pass
        for lg_name in ("trayforge.main",):
            lg = logging.getLogger(lg_name)
            for h in lg.handlers:
                h.flush()
                h.close()
        logger.info("TrayForge exited")
        os._exit(0)
