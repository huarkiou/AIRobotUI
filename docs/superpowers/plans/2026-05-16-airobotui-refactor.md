# TrayForge Refactor Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite process manager and threading model to eliminate thread contention: 3 threads (tkinter main, pystray daemon, 2×reader) with clear boundaries. Add single-instance enforcement.

**Architecture:** All Popen operations (start/stop/poll) on main thread via `root.after()`. Reader threads push to `queue.Queue`. Main thread drains queue periodically. Exit is synchronous on main thread: hide window → shutdown → quit mainloop.

---

### Task 1: Single Instance Module (new file)

**Files:** Create `single_instance.py`

- [ ] Create `single_instance.py` with Windows named mutex:

```python
"""Single-instance enforcement via Windows named mutex."""
import sys
import ctypes
from ctypes import wintypes

MUTEX_NAME = "Global\\AIRobotUI_SingleInstance"


def ensure_single_instance() -> bool:
    """Try to acquire named mutex. Returns True if we're the only instance."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True
```

- [ ] Verify: `uv run python -c "from single_instance import ensure_single_instance; assert ensure_single_instance()"`

- [ ] Commit: `feat: add single-instance mutex check`

---

### Task 2: Rewrite process_mgr.py

**Files:** Rewrite `process_mgr.py`

- [ ] Remove: monitor thread, `_monitor_running`, `start_monitor()`, `stop_monitor()`, `shutdown()` timeout wrapper
- [ ] Remove: `_manual_stop` set, restart count logic simplified
- [ ] Reader threads: push to `queue.Queue[str]` instead of callback. One queue per process.
- [ ] `_start_process`: no threading.Thread for reader, start reader thread that pushes to `self._napcat_queue` / `self._astrbot_queue`
- [ ] `_stop_process`: just `terminate()` → `wait(3s)` → `kill()` → `wait(2s)`. No taskkill. Synchronous, called from main thread only.
- [ ] Add `poll_status(name)` → return `proc.poll()` or None for external polling
- [ ] Add `drain_output(name)` → return all lines from queue (non-blocking)
- [ ] `shutdown()`: just `stop_all()`, no threads, no timeout
- [ ] Restart: poll_status detects crash → `_start_process` again if count < max

Full implementation:

```python
"""Process manager - all operations on calling thread (assumed main)."""

import subprocess
import sys
import threading
import queue
import shlex
import os
import logging
from logger import get_main_logger, get_napcat_logger, get_astrbot_logger


class ProcessManager:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._napcat_proc: subprocess.Popen | None = None
        self._astrbot_proc: subprocess.Popen | None = None
        self._napcat_restarts = 0
        self._astrbot_restarts = 0
        self._max_restarts = 3
        self._napcat_queue: queue.Queue[str] = queue.Queue()
        self._astrbot_queue: queue.Queue[str] = queue.Queue()
        self._status_listeners: list[callable] = []
        self._notify_listeners: list[callable] = []

    # --- Public API ---

    def update_config(self, config: dict) -> None:
        self._config = config

    def on_status_change(self, cb: callable) -> None:
        self._status_listeners.append(cb)

    def on_notification(self, cb: callable) -> None:
        self._notify_listeners.append(cb)

    # Process control (call from main thread only)
    def start_napcat(self) -> None: self._start("napcat")
    def start_astrbot(self) -> None: self._start("astrbot")
    def stop_napcat(self) -> None: self._stop("napcat")
    def stop_astrbot(self) -> None: self._stop("astrbot")
    def start_all(self) -> None: self.start_napcat(); self.start_astrbot()
    def stop_all(self) -> None: self.stop_napcat(); self.stop_astrbot()
    def shutdown(self) -> None: self.stop_all()

    def is_napcat_running(self) -> bool: return self._running("napcat")
    def is_astrbot_running(self) -> bool: return self._running("astrbot")

    # Called by main thread's root.after poll
    def poll_crashes(self) -> None:
        """Check both processes; if crashed unexpectedly, auto-restart or notify."""
        for name in ("napcat", "astrbot"):
            proc = self._get_proc(name)
            if proc is None:
                continue
            ret = proc.poll()
            if ret is not None:
                # Process exited
                pname = "NapCat" if name == "napcat" else "AstrBot"
                logger = get_main_logger()
                count = self._restart_count(name)
                self._set_proc(name, None)
                logger.warning("%s exited code=%d restarts=%d/%d", pname, ret, count, self._max_restarts)
                if count < self._max_restarts:
                    self._inc_restart(name)
                    self._notify(f"{pname} Crashed", f"Auto-restarting ({count + 1}/{self._max_restarts})...")
                    self._start(name)
                else:
                    self._notify(f"{pname} Stopped", "Max restarts reached.")

    def drain_napcat(self) -> list[str]:
        return self._drain_queue(self._napcat_queue)

    def drain_astrbot(self) -> list[str]:
        return self._drain_queue(self._astrbot_queue)

    # --- Internal ---

    def _drain_queue(self, q: queue.Queue) -> list[str]:
        lines = []
        while True:
            try:
                lines.append(q.get_nowait())
            except queue.Empty:
                break
        return lines

    def _name(self, n): return "NapCat" if n == "napcat" else "AstrBot"
    def _proc_attr(self, n): return "_napcat_proc" if n == "napcat" else "_astrbot_proc"
    def _restart_attr(self, n): return "_napcat_restarts" if n == "napcat" else "_astrbot_restarts"
    def _queue(self, n): return self._napcat_queue if n == "napcat" else self._astrbot_queue
    def _get_proc(self, n): return getattr(self, self._proc_attr(n))
    def _set_proc(self, n, p): setattr(self, self._proc_attr(n), p)
    def _restart_count(self, n): return getattr(self, self._restart_attr(n))
    def _inc_restart(self, n): setattr(self, self._restart_attr(n), self._restart_count(n) + 1)
    def _reset_restart(self, n): setattr(self, self._restart_attr(n), 0)
    def _running(self, n):
        p = self._get_proc(n)
        return p is not None and p.poll() is None

    def _notify(self, title: str, msg: str):
        for cb in self._notify_listeners:
            try: cb(title, msg)
            except: pass

    def _emit_status(self):
        for cb in self._status_listeners:
            try: cb()
            except: pass

    def _start(self, name: str) -> None:
        logger = get_main_logger()
        pname = self._name(name)
        if self._running(name):
            return
        cfg = self._config[name]
        cwd, cmd, enc = cfg["cwd"], cfg["cmd"], cfg.get("encoding", "utf-8")

        # Clean stale lock
        if name == "astrbot":
            lock = os.path.join(cwd, "astrbot.lock")
            if os.path.exists(lock):
                try: os.remove(lock)
                except OSError: pass

        if not os.path.exists(cwd):
            logger.error("%s cwd not found: %s", pname, cwd)
            return

        args = shlex.split(cmd)
        if not os.path.isabs(args[0]) and os.sep not in args[0] and "/" not in args[0]:
            resolved = os.path.join(cwd, args[0])
            if os.path.exists(resolved):
                args[0] = resolved

        logger.info("Starting %s: %s in %s", pname, args, cwd)
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            kwargs = dict(
                cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding=enc,
                errors="replace", env=env,
            )
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(args, **kwargs)
            self._set_proc(name, proc)
            self._reset_restart(name)
            q = self._queue(name)
            threading.Thread(target=self._reader, args=(proc.stdout, q, name), daemon=True).start()
            logger.info("%s started PID=%d", pname, proc.pid)
        except Exception as e:
            logger.error("Failed to start %s: %s", pname, e)
        self._emit_status()

    def _reader(self, pipe, q: queue.Queue, name: str):
        proc_logger = get_napcat_logger() if name == "napcat" else get_astrbot_logger()
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                if line:
                    proc_logger.info(line)
                    q.put(line)
        except (ValueError, IOError):
            pass

    def _stop(self, name: str) -> None:
        logger = get_main_logger()
        pname = self._name(name)
        proc = self._get_proc(name)
        if proc is None:
            return
        pid = proc.pid
        logger.info("Stopping %s PID=%d", pname, pid)
        # Set restart count to max to prevent auto-restart
        setattr(self, self._restart_attr(name), self._max_restarts)
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
            logger.info("%s stopped gracefully", pname)
        except subprocess.TimeoutExpired:
            logger.warning("%s not responding, killing", pname)
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
        finally:
            self._set_proc(name, None)
        self._emit_status()


import logging
```

- [ ] Verify: import and instantiate, check queue draining

- [ ] Commit: `refactor: rewrite process_mgr - single-threaded ops, queue-based output`

---

### Task 3: Rewrite tray_ui.py

**Files:** Rewrite `tray_ui.py`

- [ ] Remove all threading.Thread spawns for toggle/stop/start
- [ ] All actions just set a pending action flag that main thread picks up
- [ ] `_on_exit`: same as before (set flag, stop icon)
- [ ] Keep `_exit_requested` flag
- [ ] Add `_pending_action: tuple[str, str] | None` for start/stop/toggle from tray

```python
"""System tray - minimal code, dispatches actions to main thread."""

import threading
import pystray
from pystray import Menu, MenuItem
from icon import get_green_icon, get_yellow_icon, get_red_icon
from logger import get_main_logger


class TrayUI:
    def __init__(self, process_mgr, main_window, config):
        self._pm = process_mgr
        self._window = main_window
        self._logger = get_main_logger()
        self._config_callback = None
        self._exit_requested = False
        self._pending_action: str | None = None  # "start:napcat", "stop:astrbot", "start:all", "stop:all"

        self._icon = pystray.Icon("AIRobotUI", get_red_icon(), "AIRobotUI", menu=self._build_menu())
        self._pm.on_status_change(self._refresh_icon)
        self._pm.on_notification(self._on_notify)

    def set_config_callback(self, cb): self._config_callback = cb

    # --- Menu ---
    def _build_menu(self):
        return Menu(
            MenuItem("NapCat", self._status_menu("napcat")),
            MenuItem("AstrBot", self._status_menu("astrbot")),
            Menu.SEPARATOR,
            MenuItem("Start All", lambda i, _: self._enqueue("start:all")),
            MenuItem("Stop All", lambda i, _: self._enqueue("stop:all")),
            Menu.SEPARATOR,
            MenuItem("Show Window", lambda i, _: self._window.root.after(0, self._window.show)),
            MenuItem("Settings", lambda i, _: self._cb_settings()),
            Menu.SEPARATOR,
            MenuItem("Exit", lambda i, _: self._do_exit(i)),
        )

    def _status_menu(self, name):
        def toggle(icon, item):
            action = "stop" if (name == "napcat" and self._pm.is_napcat_running()) or (name == "astrbot" and self._pm.is_astrbot_running()) else "start"
            self._enqueue(f"{action}:{name}")

        def text(_):
            running = self._pm.is_napcat_running() if name == "napcat" else self._pm.is_astrbot_running()
            return f"  {'●' if running else '○'} {'Running' if running else 'Stopped'}"

        return Menu(MenuItem(text, toggle))

    def _enqueue(self, action: str):
        self._pending_action = action

    def consume_action(self) -> str | None:
        a = self._pending_action
        self._pending_action = None
        return a

    def _cb_settings(self):
        if self._config_callback:
            self._window.root.after(0, self._config_callback)

    def _do_exit(self, icon):
        self._logger.info("Exit requested")
        self._exit_requested = True
        icon.stop()

    def _refresh_icon(self):
        nr = self._pm.is_napcat_running()
        ar = self._pm.is_astrbot_running()
        if nr and ar: self._icon.icon = get_green_icon()
        elif nr or ar: self._icon.icon = get_yellow_icon()
        else: self._icon.icon = get_red_icon()
        self._icon.menu = self._build_menu()

    def _on_notify(self, title, msg):
        try: self._icon.notify(msg, title)
        except: pass

    def run(self):
        threading.Thread(target=self._icon.run, daemon=True, name="tray-icon").start()
```

- [ ] Verify import

- [ ] Commit: `refactor: rewrite tray_ui - action queue instead of background threads`

---

### Task 4: Rewrite main.pyw (event loop + single instance)

**Files:** Rewrite `main.pyw`

- [ ] Single instance check at startup, exit if already running
- [ ] Main loop: `root.after(100)` for `_tick()` which does:
  - Consume pending tray action → execute
  - Drain output queues → push to window
  - Poll process crashes → auto-restart
  - Check exit flag → shutdown → quit
- [ ] Exit: `_exit_requested` → `window.hide()` → `pm.shutdown()` → `root.quit()`
- [ ] After mainloop: `window.destroy()`, sleep 0.5s

```python
"""AIRobotUI - tray controller for NapCat QQ and AstrBot."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from single_instance import ensure_single_instance
from logger import get_main_logger
from config import load_config, get_default_config, save_config
from process_mgr import ProcessManager
from main_window import MainWindow
from config_ui import ConfigDialog
from tray_ui import TrayUI


def main():
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

    _settings_open = False

    def open_settings():
        nonlocal _settings_open
        if _settings_open:
            return
        _settings_open = True
        try:
            dlg = ConfigDialog(window.root)
            result = dlg.get_result()
            if result is not None:
                pm.update_config(result)
        finally:
            _settings_open = False

    tray.set_config_callback(open_settings)

    # --- Main event tick (runs every 100ms on main thread) ---
    POLL_INTERVAL = 2000  # Process crash poll interval
    _last_poll = 0

    def _tick():
        nonlocal _last_poll

        # 1. Consume pending tray action
        action = tray.consume_action()
        if action:
            logger.info("Action: %s", action)
            if action == "start:all": pm.start_all()
            elif action == "stop:all": pm.stop_all()
            elif action == "start:napcat": pm.start_napcat()
            elif action == "stop:napcat": pm.stop_napcat()
            elif action == "start:astrbot": pm.start_astrbot()
            elif action == "stop:astrbot": pm.stop_astrbot()

        # 2. Drain output to window
        for line in pm.drain_napcat():
            window.append_output("NapCat", line)
        for line in pm.drain_astrbot():
            window.append_output("AstrBot", line)

        # 3. Periodic crash poll
        now = time.monotonic() * 1000
        if now - _last_poll >= POLL_INTERVAL:
            _last_poll = now
            pm.poll_crashes()

        # 4. Exit check
        if tray._exit_requested:
            logger.info("Exit: hiding window, shutting down...")
            window.hide()
            pm.shutdown()
            window.root.quit()
            return  # Stop the tick loop

        window.root.after(100, _tick)

    # --- Setup ---
    if is_first:
        window.root.after(300, open_settings)

    tray.run()
    window.root.after(100, _tick)
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
```

- [ ] Verify import, check single instance behavior

- [ ] Commit: `refactor: rewrite main.pyw - unified event tick on main thread`

---

### Task 5: Clean up and verify

- [ ] Remove unused imports across all files
- [ ] Verify all modules import: `uv run python -c "from process_mgr import ProcessManager; from tray_ui import TrayUI; from main_window import MainWindow; from single_instance import ensure_single_instance; print('OK')"`
- [ ] Build EXE
- [ ] Commit: `chore: cleanup and final verification`
