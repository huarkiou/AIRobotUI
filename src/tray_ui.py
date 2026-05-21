"""System tray — dynamic menus for all managed processes."""

import threading
import pystray
from pystray import Menu, MenuItem
from typing import Callable
from icon import get_green_icon, get_yellow_icon, get_red_icon
from logger import get_main_logger
from trayforge_types import AppConfig


class TrayUI:
    def __init__(self, process_mgr, main_window, config: AppConfig) -> None:
        self._pm = process_mgr
        self._window = main_window
        self._logger = get_main_logger()
        self._config_callback: Callable[[], None] | None = None
        self._exit_requested = False
        self._pending_action: str | None = None

        self._icon = pystray.Icon(
            "TrayForge",
            get_red_icon(),
            "TrayForge",
            menu=self._build_menu(),
        )
        self._pm.on_status_change(self._refresh_icon)
        self._pm.on_notification(self._on_notify)

    def set_config_callback(self, cb: Callable[[], None]) -> None:
        self._config_callback = cb

    def consume_action(self) -> str | None:
        a = self._pending_action
        self._pending_action = None
        return a

    # --- Menu ---

    def _build_menu(self) -> Menu:
        items = []
        for name in self._pm.process_names():
            items.append(MenuItem(name, self._status_menu(name)))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Start All", lambda i, _: self._enqueue("startall")))
        items.append(MenuItem("Stop All", lambda i, _: self._enqueue("stopall")))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Reload Config", lambda i, _: self._enqueue("reload")))
        items.append(Menu.SEPARATOR)
        items.append(
            MenuItem(
                "Show/Hide Window",
                lambda i, _: self._window.root.after(0, self._window.toggle),
            )
        )
        items.append(MenuItem("Settings", lambda i, _: self._cb_settings()))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Exit", lambda i, _: self._do_exit(i)))
        return Menu(*items)

    def _status_menu(self, name: str) -> Menu:
        def toggle(icon, item):
            running = self._pm.is_running(name)
            action = "stop" if running else "start"
            self._enqueue(f"{action}:{name}")

        def text(_) -> str:
            running = self._pm.is_running(name)
            indicator = "\u25cf" if running else "\u25cb"
            status = "Running" if running else "Stopped"
            return f"  {indicator} {status}"

        def webui_label(_) -> str:
            return f"  {self._pm.get_webui_url(name)}"

        def webui_visible(_) -> bool:
            if not self._pm.is_running(name):
                return False
            if not self._pm.has_webui(name):
                return False
            return self._pm.get_webui_url(name) is not None

        def open_webui(icon, item):
            self._enqueue(f"webui:{name}")

        items = [MenuItem(text, toggle)]
        if self._pm.has_webui(name):
            items.append(MenuItem(webui_label, open_webui, visible=webui_visible))
        return Menu(*items)

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
        names = self._pm.process_names()
        running_count = sum(1 for n in names if self._pm.is_running(n))
        total = len(names)
        if total == 0:
            self._icon.icon = get_red_icon()
        elif running_count == total:
            self._icon.icon = get_green_icon()
        elif running_count > 0:
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
        threading.Thread(target=self._icon.run, daemon=True, name="tray-icon").start()
