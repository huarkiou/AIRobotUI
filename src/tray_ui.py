"""System tray - minimal code, dispatches actions to main thread."""

import threading
import webbrowser
import re
import pystray
from pystray import Menu, MenuItem
from icon import get_green_icon, get_yellow_icon, get_red_icon
from logger import get_main_logger


class TrayUI:
    def __init__(self, process_mgr, main_window, config) -> None:
        self._pm = process_mgr
        self._window = main_window
        self._logger = get_main_logger()
        self._config_callback: callable | None = None
        self._exit_requested = False
        self._pending_action: str | None = None

        self._icon = pystray.Icon(
            "AIRobotUI",
            get_red_icon(),
            "AIRobotUI",
            menu=self._build_menu(),
        )
        self._pm.on_status_change(self._refresh_icon)
        self._pm.on_notification(self._on_notify)

    def set_config_callback(self, cb: callable) -> None:
        self._config_callback = cb

    def consume_action(self) -> str | None:
        a = self._pending_action
        self._pending_action = None
        return a

    # --- Menu ---

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem("NapCat", self._status_menu("napcat")),
            MenuItem("AstrBot", self._status_menu("astrbot")),
            Menu.SEPARATOR,
            MenuItem("Start All", lambda i, _: self._enqueue("start:all")),
            MenuItem("Stop All", lambda i, _: self._enqueue("stop:all")),
            Menu.SEPARATOR,
            MenuItem(
                "Show/Hide Window",
                lambda i, _: self._window.root.after(0, self._window.toggle),
            ),
            MenuItem("Settings", lambda i, _: self._cb_settings()),
            Menu.SEPARATOR,
            MenuItem("Exit", lambda i, _: self._do_exit(i)),
        )

    def _status_menu(self, name: str) -> Menu:
        def toggle(icon, item):
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            action = "stop" if running else "start"
            self._enqueue(f"{action}:{name}")

        def text(_) -> str:
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            indicator = "\u25CF" if running else "\u25CB"
            status = "Running" if running else "Stopped"
            return f"  {indicator} {status}"

        def webui_label(_) -> str:
            url = (
                self._pm.get_napcat_webui_url()
                if name == "napcat"
                else self._pm.get_astrbot_webui_url()
            )
            if url:
                m = re.search(r"https?://([^/\s]+)", url)
                host = m.group(1) if m else ""
                return f"  Open WebUI ({host})" if host else "  Open WebUI"
            return "  Open WebUI"

        def webui_visible(_) -> bool:
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            if not running:
                return False
            url = (
                self._pm.get_napcat_webui_url()
                if name == "napcat"
                else self._pm.get_astrbot_webui_url()
            )
            return url is not None

        def open_webui(icon, item):
            self._enqueue(f"webui:{name}")

        return Menu(
            MenuItem(text, toggle),
            MenuItem(webui_label, open_webui, visible=webui_visible),
        )

    def _enqueue(self, action: str) -> None:
        self._pending_action = action

    def _cb_settings(self) -> None:
        if self._config_callback:
            self._window.root.after(0, self._config_callback)

    def _do_exit(self, icon) -> None:
        self._logger.info("Exit requested")
        self._exit_requested = True
        icon.stop()

    def _refresh_icon(self) -> None:
        nr = self._pm.is_napcat_running()
        ar = self._pm.is_astrbot_running()
        if nr and ar:
            self._icon.icon = get_green_icon()
        elif nr or ar:
            self._icon.icon = get_yellow_icon()
        else:
            self._icon.icon = get_red_icon()
        self._icon.menu = self._build_menu()

    def _on_notify(self, title: str, msg: str) -> None:
        try:
            self._icon.notify(msg, title)
        except Exception:
            pass

    # --- Lifecycle ---

    def run(self) -> None:
        self._logger.info("Starting tray icon in background thread")
        threading.Thread(
            target=self._icon.run, daemon=True, name="tray-icon"
        ).start()
