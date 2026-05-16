"""System tray icon and menu for AIRobotUI."""

import threading
import pystray
from pystray import Menu, MenuItem
from icon import get_green_icon, get_yellow_icon, get_red_icon
from logger import get_main_logger
from process_mgr import ProcessManager
from main_window import MainWindow


class TrayUI:
    def __init__(
        self,
        process_mgr: ProcessManager,
        main_window: MainWindow,
        config: dict,
    ) -> None:
        self._pm = process_mgr
        self._window = main_window
        self._config = config
        self._logger = get_main_logger()
        self._config_callback: callable | None = None

        # Create initial icon
        self._icon = pystray.Icon(
            "AIRobotUI",
            get_red_icon(),
            "AIRobotUI",
            menu=self._build_menu(),
        )

        # Register callbacks
        self._pm.on_status_change(self._refresh_icon)
        self._pm.on_notification(self._on_notification)

    def set_config_callback(self, callback: callable) -> None:
        """Set callback to be called when settings dialog is opened."""
        self._config_callback = callback

    # --- Menu Building ---

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(
                "NapCat",
                self._make_status_submenu("napcat"),
                enabled=True,
            ),
            MenuItem(
                "AstrBot",
                self._make_status_submenu("astrbot"),
                enabled=True,
            ),
            Menu.SEPARATOR,
            MenuItem("Start All", self._on_start_all),
            MenuItem("Stop All", self._on_stop_all),
            Menu.SEPARATOR,
            MenuItem("Show Window", self._on_show_window),
            MenuItem("Settings", self._on_settings),
            Menu.SEPARATOR,
            MenuItem("Exit", self._on_exit),
        )

    def _make_status_submenu(self, name: str) -> Menu:
        def _toggle(icon, item):
            self._on_toggle(name)
            self._refresh_icon()

        def _status_text(_):
            if name == "napcat":
                running = self._pm.is_napcat_running()
            else:
                running = self._pm.is_astrbot_running()
            indicator = "\u25CF" if running else "\u25CB"  # ● or ○
            status = "Running" if running else "Stopped"
            return f"  {indicator} {status}"

        return Menu(
            MenuItem(
                _status_text,
                _toggle,
            ),
        )

    def _refresh_icon(self) -> None:
        """Update tray icon based on process status."""
        napcat_running = self._pm.is_napcat_running()
        astrbot_running = self._pm.is_astrbot_running()

        if napcat_running and astrbot_running:
            self._icon.icon = get_green_icon()
        elif napcat_running or astrbot_running:
            self._icon.icon = get_yellow_icon()
        else:
            self._icon.icon = get_red_icon()

        # Rebuild menu to reflect updated status text
        self._icon.menu = self._build_menu()

    # --- Actions (all run in background thread to keep tray responsive) ---

    def _on_toggle(self, name: str) -> None:
        """Toggle a process - runs in background thread."""
        def _toggle():
            if name == "napcat":
                if self._pm.is_napcat_running():
                    self._pm.stop_napcat()
                else:
                    self._pm.start_napcat()
            else:
                if self._pm.is_astrbot_running():
                    self._pm.stop_astrbot()
                else:
                    self._pm.start_astrbot()
        threading.Thread(target=_toggle, daemon=True, name=f"toggle-{name}").start()

    def _on_start_all(self, icon, item) -> None:
        threading.Thread(target=self._pm.start_all, daemon=True, name="start-all").start()

    def _on_stop_all(self, icon, item) -> None:
        threading.Thread(target=self._pm.stop_all, daemon=True, name="stop-all").start()

    def _on_show_window(self, icon, item) -> None:
        self._window.root.after(0, self._window.show)

    def _on_settings(self, icon, item) -> None:
        if self._config_callback:
            self._window.root.after(0, self._config_callback)

    def _on_exit(self, icon, item) -> None:
        """Exit: stop icon first (must be from pystray thread), then shutdown in background."""
        self._logger.info("Exit requested from tray menu")
        icon.stop()  # Must be called from pystray thread

        def _cleanup():
            self._pm.shutdown()
            self._window.root.after(0, self._window.destroy)

        threading.Thread(target=_cleanup, daemon=True, name="exit-cleanup").start()

    def _on_notification(self, title: str, message: str) -> None:
        """Handle notification from process manager."""
        try:
            self._icon.notify(message, title)
        except Exception:
            pass

    # --- Lifecycle ---

    def run(self) -> None:
        """Start the tray icon in a background daemon thread (non-blocking)."""
        self._logger.info("Starting tray icon in background thread")
        tray_thread = threading.Thread(
            target=self._icon.run, daemon=True, name="tray-icon"
        )
        tray_thread.start()

    def stop(self) -> None:
        """Stop the tray icon."""
        self._icon.stop()
