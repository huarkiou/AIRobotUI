# Generic Process Manager + Llama.cpp Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor ProcessManager from hardcoded NapCat/AstrBot pairs to a generic process registry, add llama.cpp control, fix Windows taskbar icon.

**Architecture:** Replace all paired `_napcat_*` / `_astrbot_*` attributes with a `_procs: dict[str, _ProcState]` keyed by name. Config moves to a `processes[]` array. UI layers (MainWindow tabs, TrayUI menu, ConfigDialog) become dynamic, driven by process names. Backward-compatible config migration on first load.

**Tech Stack:** Python 3.11+, tkinter, pystray, Pillow, psutil, ctypes (taskbar fix)

---

## Task 1: icon.py — add save_ico() for taskbar icon

**Files:**
- Modify: `src/icon.py`

- [ ] **Step 1: Add save_ico() function and os import**

Add to `src/icon.py`:

```python
import os


def save_ico(path: str) -> None:
    """Save the blue app icon as a multi-resolution .ico file for taskbar."""
    icon = get_app_icon()
    icon.save(path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
```

- [ ] **Step 2: Verify the file parses correctly**

Run: `uv run python -c "from src.icon import save_ico; print('OK')"`
Expected: `OK` (no errors)

- [ ] **Step 3: Commit**

```bash
git add src/icon.py
git commit -m "feat(icon): add save_ico() for taskbar icon"
```

---

## Task 2: logger.py — add get_process_logger()

**Files:**
- Modify: `src/logger.py`

- [ ] **Step 1: Add get_process_logger() and backward-compat wrappers**

Add `import re` at top, then append before module-level singletons:

```python
def get_process_logger(name: str) -> logging.Logger:
    """Get a logger for a managed process. Name is sanitized to a safe filename."""
    safe = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff-]", "_", name).strip("_") or "process"
    return _create_logger(f"airobotui.process.{safe}", f"{safe}.log")


# Backward-compat wrappers
def get_napcat_logger() -> logging.Logger:
    return get_process_logger("NapCat")


def get_astrbot_logger() -> logging.Logger:
    return get_process_logger("AstrBot")
```

- [ ] **Step 2: Verify imports and function**

Run: `uv run python -c "from src.logger import get_process_logger, get_napcat_logger; l = get_process_logger('Llama'); print(l.name); print(get_napcat_logger().name)"`
Expected: `airobotui.process.Llama` and `airobotui.process.NapCat`

- [ ] **Step 3: Commit**

```bash
git add src/logger.py
git commit -m "feat(logger): add get_process_logger() with backward-compat wrappers"
```

---

## Task 3: config.py — new schema + old-format migration

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Rewrite get_default_config()**

Replace `get_default_config()` body with:

```python
def get_default_config() -> dict:
    """Return default configuration with processes array."""
    return {
        "processes": [
            {
                "name": "NapCat",
                "cwd": "D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell",
                "cmd": "NapCatWinBootMain.exe 2450085301",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?://\\S+)",
                "delete_before_start": [],
            },
            {
                "name": "AstrBot",
                "cwd": "D:\\Apps\\ai\\AIRobotUI\\astrbot",
                "cmd": "astrbot run",
                "encoding": "utf-8",
                "singleton": True,
                "autostart": False,
                "webui_pattern": "Starting WebUI at (https?://\\S+)",
                "delete_before_start": ["astrbot.lock"],
            },
        ],
        "output_refresh_ms": 500,
        "autostart": False,
    }
```

- [ ] **Step 2: Add _migrate_old_config() before load_config()**

```python
def _migrate_old_config(old: dict) -> dict:
    """Convert old {napcat:{...}, astrbot:{...}} format to processes[] array."""
    logger = get_main_logger()
    logger.info("Migrating old config format to new processes[] schema")
    processes = []
    for key in ("napcat", "astrbot"):
        if key in old:
            proc = old[key]
            processes.append({
                "name": "NapCat" if key == "napcat" else "AstrBot",
                "cwd": proc.get("cwd", ""),
                "cmd": proc.get("cmd", ""),
                "encoding": proc.get("encoding", "utf-8"),
                "singleton": True,
                "autostart": old.get("autostart", False),
                "webui_pattern": (
                    "\\[WebUi\\] WebUi User Panel Url: (https?://\\S+)"
                    if key == "napcat"
                    else "Starting WebUI at (https?://\\S+)"
                ),
                "delete_before_start": ["astrbot.lock"] if key == "astrbot" else [],
            })
    return {
        "processes": processes,
        "output_refresh_ms": old.get("output_refresh_ms", 500),
        "autostart": old.get("autostart", False),
    }
```

- [ ] **Step 3: Modify load_config() to detect and migrate old format**

In `load_config()`, after `config = json.load(f)` and before `logger.info("Config loaded...")`, insert:

```python
        if "processes" not in config:
            config = _migrate_old_config(config)
            save_config(config)
```

- [ ] **Step 4: Verify migration with a synthetic old config**

Create a test script or run interactively:

```bash
uv run python -c "
import json, os, sys
sys.path.insert(0, 'src')
os.environ['LOCALAPPDATA'] = os.path.join(os.getcwd(), 'test_data')
from config import load_config, save_config, get_default_config, get_data_dir
data_dir = get_data_dir()
os.makedirs(data_dir, exist_ok=True)
old = {'napcat': {'cwd': 'X', 'cmd': 'Y', 'encoding': 'u'}, 'astrbot': {'cwd': 'A', 'cmd': 'B', 'encoding': 'u'}, 'output_refresh_ms': 300}
with open(os.path.join(data_dir, 'config.json'), 'w') as f:
    json.dump(old, f)
cfg = load_config()
print('has processes:', 'processes' in cfg)
print('count:', len(cfg['processes']))
print('NapCat name:', cfg['processes'][0]['name'])
"
```
Expected: `has processes: True`, `count: 2`, `NapCat name: NapCat`

- [ ] **Step 5: Clean up test data and commit**

```bash
rm -rf test_data
git add src/config.py
git commit -m "feat(config): processes[] schema with old-format migration"
```

---

## Task 4: process_mgr.py — full refactor to generic ProcessManager

**Files:**
- Modify: `src/process_mgr.py`

This is the largest change. The file is rewritten entirely while preserving all existing logic in generalized form.

- [ ] **Step 1: Replace the entire file with the generic version**

Write `src/process_mgr.py`:

```python
"""Process manager — generic dict-based process registry."""

from dataclasses import dataclass, field
import subprocess
import sys
import threading
import queue
import shlex
import os
import re
import time
from datetime import datetime
import psutil
from logger import get_main_logger, get_process_logger


_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

MAX_RESTARTS = 3
RESTART_COOLDOWN = 60.0


@dataclass
class _ProcState:
    proc: subprocess.Popen | None = None
    queue: queue.Queue = field(default_factory=queue.Queue)
    restarts: int = 0
    webui_url: str | None = None
    last_restart: float = 0.0
    cooldown_notified: bool = False
    cfg: dict = field(default_factory=dict)


class ProcessManager:
    def __init__(self, config: dict) -> None:
        self._procs: dict[str, _ProcState] = {}
        self._status_listeners: list[callable] = []
        self._notify_listeners: list[callable] = []
        self._build_from_config(config)

    # --- Public API ---

    def update_config(self, config: dict) -> None:
        self._build_from_config(config)
        self._emit_status()

    def process_names(self) -> list[str]:
        return list(self._procs.keys())

    def on_status_change(self, cb: callable) -> None:
        self._status_listeners.append(cb)

    def on_notification(self, cb: callable) -> None:
        self._notify_listeners.append(cb)

    def start(self, name: str) -> None:
        self._start(name)

    def stop(self, name: str) -> None:
        self._stop(name)

    def start_all(self) -> None:
        for name in self._procs:
            self._start(name)

    def stop_all(self) -> None:
        for name in self._procs:
            self._stop(name)

    def shutdown(self) -> None:
        self.stop_all()

    def is_running(self, name: str) -> bool:
        ps = self._procs.get(name)
        if ps is None:
            return False
        return ps.proc is not None and ps.proc.poll() is None

    def has_webui(self, name: str) -> bool:
        ps = self._procs.get(name)
        if ps is None:
            return False
        return ps.cfg.get("webui_pattern") is not None

    def get_webui_url(self, name: str) -> str | None:
        ps = self._procs.get(name)
        if ps is None:
            return None
        return ps.webui_url

    def drain(self, name: str) -> list[str]:
        ps = self._procs.get(name)
        if ps is None:
            return []
        lines: list[str] = []
        q = ps.queue
        while True:
            try:
                lines.append(q.get_nowait())
            except queue.Empty:
                break
        return lines

    def poll_crashes(self) -> None:
        for name, ps in self._procs.items():
            if ps.proc is None:
                continue
            ret = ps.proc.poll()
            if ret is not None:
                if ps.restarts >= MAX_RESTARTS:
                    ps.proc = None
                    ps.webui_url = None
                    self._system_msg(
                        name,
                        f"{name} max restart attempts ({MAX_RESTARTS}) reached, stopped",
                    )
                    self._notify(
                        f"{name} Stopped", "Max restart attempts reached."
                    )
                    self._emit_status()
                    continue

                now = time.monotonic()
                if ps.restarts > 0 and now - ps.last_restart < RESTART_COOLDOWN:
                    if not ps.cooldown_notified:
                        ps.cooldown_notified = True
                        remaining = int(RESTART_COOLDOWN - (now - ps.last_restart))
                        self._system_msg(
                            name,
                            f"{name} restart cooldown, next attempt in {remaining}s",
                        )
                    continue

                ps.proc = None
                ps.webui_url = None
                ps.restarts += 1
                ps.cooldown_notified = False
                ps.last_restart = now
                self._system_msg(
                    name,
                    f"{name} exited (code={ret}), auto-restarting ({ps.restarts}/{MAX_RESTARTS})...",
                )
                self._notify(
                    f"{name} Crashed",
                    f"Auto-restarting ({ps.restarts}/{MAX_RESTARTS})...",
                )
                self._start(name, _reset_counter=False)
                self._emit_status()

    # --- Internal ---

    def _build_from_config(self, config: dict) -> None:
        new_procs: dict[str, _ProcState] = {}
        for proc_cfg in config.get("processes", []):
            name = proc_cfg["name"]
            if name in self._procs:
                existing = self._procs[name]
                existing.cfg = proc_cfg
                new_procs[name] = existing
            else:
                new_procs[name] = _ProcState(cfg=proc_cfg)
        for old_name in self._procs:
            if old_name not in new_procs:
                self._stop_internal(old_name)
        self._procs = new_procs

    def _system_msg(self, name: str, msg: str) -> None:
        ps = self._procs.get(name)
        if ps is None:
            return
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        ps.queue.put(f"[{ts}] [SYSTEM] {msg}")

    def _notify(self, title: str, msg: str) -> None:
        for cb in self._notify_listeners:
            try:
                cb(title, msg)
            except Exception:
                pass

    def _emit_status(self) -> None:
        for cb in self._status_listeners:
            try:
                cb()
            except Exception:
                pass

    def _kill_cwd_processes(self, cwd: str) -> None:
        """Kill all processes whose cwd matches the given directory."""
        if not cwd:
            return
        norm_cwd = os.path.normpath(cwd)
        try:
            for proc in psutil.process_iter(["pid", "cwd"]):
                try:
                    p_cwd = proc.info["cwd"]
                    if p_cwd and os.path.normpath(p_cwd) == norm_cwd:
                        subprocess.run(
                            ["taskkill", "/f", "/t", "/pid", str(proc.info["pid"])],
                            capture_output=True,
                            timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                    pass
        except Exception:
            pass

    def _start(self, name: str, _reset_counter: bool = True) -> None:
        logger = get_main_logger()
        ps = self._procs.get(name)
        if ps is None:
            return
        if self.is_running(name):
            return

        cfg = ps.cfg
        cwd: str = cfg.get("cwd", "")
        cmd: str = cfg.get("cmd", "")
        enc: str = cfg.get("encoding", "utf-8")
        singleton: bool = cfg.get("singleton", False)
        delete_files: list[str] = cfg.get("delete_before_start", [])

        # Singleton: kill all processes matching cwd
        if singleton and sys.platform == "win32":
            self._kill_cwd_processes(cwd)

        # Delete files before start
        for rel_path in delete_files:
            file_path = os.path.join(cwd, rel_path) if cwd else rel_path
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except PermissionError:
                    if sys.platform == "win32":
                        self._kill_cwd_processes(cwd)
                        time.sleep(0.3)
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        logger.warning("Failed to delete %s: %s", file_path, e)

        if cwd and not os.path.exists(cwd):
            logger.error("%s cwd not found: %s", name, cwd)
            return

        args = shlex.split(cmd)
        if not os.path.isabs(args[0]) and os.sep not in args[0] and "/" not in args[0]:
            if cwd:
                resolved = os.path.join(cwd, args[0])
                if os.path.exists(resolved):
                    args[0] = resolved

        logger.info("Starting %s: %s", name, args)
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            kwargs: dict = {
                "cwd": cwd or None,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": enc,
                "errors": "replace",
                "env": env,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(args, **kwargs)
            ps.proc = proc
            if _reset_counter:
                ps.restarts = 0
            threading.Thread(
                target=self._reader,
                args=(proc.stdout, ps.queue, name, ps),
                daemon=True,
            ).start()
            logger.info("%s started PID=%d", name, proc.pid)
            self._system_msg(name, f"{name} started (PID={proc.pid})")
        except Exception as e:
            logger.error("Failed to start %s: %s", name, e)
        self._emit_status()

    def _stop(self, name: str) -> None:
        self._stop_internal(name)
        self._emit_status()

    def _stop_internal(self, name: str) -> None:
        logger = get_main_logger()
        ps = self._procs.get(name)
        if ps is None or ps.proc is None:
            return
        pid = ps.proc.pid
        logger.info("Stopping %s PID=%d", name, pid)
        ps.restarts = MAX_RESTARTS
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/f", "/t", "/pid", str(pid)],
                capture_output=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                ps.proc.terminate()
                ps.proc.wait(timeout=2)
            except Exception:
                try:
                    ps.proc.kill()
                except Exception:
                    pass
        ps.proc = None
        ps.webui_url = None
        self._system_msg(name, f"{name} stopped")

    def _reader(
        self, pipe, q: queue.Queue, name: str, ps: _ProcState
    ) -> None:
        proc_logger = get_process_logger(name)
        url_parsed = False
        webui_pattern_str = ps.cfg.get("webui_pattern")
        webui_re = re.compile(webui_pattern_str) if webui_pattern_str else None
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                line = _STRIP_ANSI.sub("", line)
                if line:
                    proc_logger.info(line)
                    q.put(line)
                    if not url_parsed and webui_re is not None:
                        m = webui_re.search(line)
                        if m:
                            ps.webui_url = m.group(1)
                            url_parsed = True
                            self._emit_status()
        except (ValueError, IOError):
            pass
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from src.process_mgr import ProcessManager, _ProcState; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/process_mgr.py
git commit -m "refactor(process_mgr): generic dict-based ProcessManager"
```

---

## Task 5: main_window.py — dynamic tabs + taskbar icon fix

**Files:**
- Modify: `src/main_window.py`

- [ ] **Step 1: Add taskbar icon fix and ctypes import**

Replace the file with the new version that has dynamic tabs and taskbar icon:

```python
"""Main window with dynamic tabs for all managed processes."""

import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from icon import get_app_icon, save_ico
from config import get_data_dir
from logger import get_main_logger
import sys
import os

MAX_LINES = 5000


class MainWindow:
    def __init__(self) -> None:
        # Taskbar icon fix: must be set BEFORE Tk() on Windows
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIRobotUI")

        self.root = tk.Tk()
        self.root.title("AIRobotUI - Process Control")
        self._tk_icon = ImageTk.PhotoImage(get_app_icon())
        self.root.iconphoto(True, self._tk_icon)

        # Taskbar icon via .ico file
        if sys.platform == "win32":
            ico_path = os.path.join(get_data_dir(), "icon.ico")
            save_ico(ico_path)
            self.root.iconbitmap(default=ico_path)

        self.root.geometry("800x500")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 800) // 2
        y = (sh - 500) // 2
        self.root.geometry(f"800x500+{x}+{y}")

        # Notebook (tabs) — dynamic, populated by set_processes()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._tabs: dict[str, tk.Text] = {}  # name -> Text widget

        self._visible = False
        self._close_callback: callable | None = None
        self._logger = get_main_logger()

        self.root.withdraw()

    def set_processes(self, names: list[str]) -> None:
        """Rebuild tabs to match the given process name list. Preserves existing tabs."""
        # Remove tabs not in names
        for name in list(self._tabs.keys()):
            if name not in names:
                # Each tab has: notebook -> frame -> Frame -> Text
                text_widget = self._tabs[name]
                outer_frame = text_widget.master.master  # ttk.Frame
                self.notebook.forget(outer_frame)
                del self._tabs[name]

        # Add new tabs
        for name in names:
            if name not in self._tabs:
                frame = ttk.Frame(self.notebook)
                self.notebook.add(frame, text=name)
                text = self._create_text_widget(frame)
                self._tabs[name] = text

    def _create_text_widget(self, parent: ttk.Frame) -> tk.Text:
        """Create a read-only text widget with Clear button at bottom."""
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            text_frame,
            bg="white",
            fg="black",
            insertbackground="black",
            font=("Microsoft YaHei", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
        )
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        context_menu = tk.Menu(text, tearoff=0)
        context_menu.add_command(label="Clear", command=lambda t=text: self._clear_tab(t))
        context_menu.add_command(label="Copy", command=lambda t=text: self._copy_selection(t))
        text.bind(
            "<Button-3>",
            lambda e, m=context_menu: m.tk_popup(e.x_root, e.y_root),
        )

        return text

    def _clear_tab(self, text: tk.Text) -> None:
        text.config(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.config(state=tk.DISABLED)

    def _copy_selection(self, text: tk.Text) -> None:
        try:
            sel = text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
        except tk.TclError:
            pass

    def set_on_close(self, callback: callable) -> None:
        self._close_callback = callback

    def _on_close(self) -> None:
        self.root.withdraw()
        self._visible = False
        self._logger.info("Main window hidden")
        if self._close_callback:
            self._close_callback()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._visible = True
        self._logger.info("Main window shown")

    def hide(self) -> None:
        self.root.withdraw()
        self._visible = False

    def toggle(self) -> None:
        if self._visible:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.after(150, self.hide)
        else:
            self.show()

    def is_visible(self) -> bool:
        return self._visible

    def append_output(self, process_name: str, line: str) -> None:
        self.root.after(0, self._append_output_impl, process_name, line)

    def _append_output_impl(self, process_name: str, line: str) -> None:
        text = self._tabs.get(process_name)
        if text is None:
            return

        text.config(state=tk.NORMAL)
        text.insert(tk.END, line + "\n")

        line_count = int(text.index("end-1c").split(".")[0])
        if line_count > MAX_LINES:
            excess = line_count - MAX_LINES
            text.delete("1.0", f"{excess}.0")

        text.config(state=tk.DISABLED)
        text.see(tk.END)

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
```

- [ ] **Step 2: Verify module imports**

```bash
uv run python -c "from src.main_window import MainWindow; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/main_window.py
git commit -m "feat(main_window): dynamic process tabs + taskbar icon fix"
```

---

## Task 6: tray_ui.py — dynamic submenus

**Files:**
- Modify: `src/tray_ui.py`

- [ ] **Step 1: Replace with dynamic version**

```python
"""System tray — dynamic menus for all managed processes."""

import threading
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
        items = []
        for name in self._pm.process_names():
            items.append(MenuItem(name, self._status_menu(name)))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Start All", lambda i, _: self._enqueue("startall")))
        items.append(MenuItem("Stop All", lambda i, _: self._enqueue("stopall")))
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
            url = self._pm.get_webui_url(name)
            if url:
                m = re.search(r"https?://([^/\s]+)", url)
                host = m.group(1) if m else ""
                return f"  Open WebUI ({host})" if host else "  Open WebUI"
            return "  Open WebUI"

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
```

- [ ] **Step 2: Verify module imports**

```bash
uv run python -c "from src.tray_ui import TrayUI; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/tray_ui.py
git commit -m "refactor(tray_ui): dynamic menus from process registry"
```

---

## Task 7: config_ui.py — dynamic scrollable settings dialog

**Files:**
- Modify: `src/config_ui.py`

- [ ] **Step 1: Replace with dynamic version**

```python
"""Configuration dialog for AIRobotUI — dynamic process list editor."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk
from icon import get_app_icon
from config import load_config, save_config, get_default_config
from startup import enable_autostart, disable_autostart, is_autostart_enabled
from logger import get_main_logger


class ConfigDialog:
    def __init__(self, root: tk.Tk) -> None:
        self._logger = get_main_logger()
        self._result: dict | None = None
        self._root_was_hidden = False

        self.dialog = tk.Toplevel(root)
        self.dialog.title("AIRobotUI - Settings")
        self._tk_icon = ImageTk.PhotoImage(get_app_icon())
        self.dialog.iconphoto(True, self._tk_icon)
        self.dialog.geometry("650x520")
        self.dialog.resizable(False, False)
        self.dialog.transient(root)

        # Center relative to parent
        self.dialog.update_idletasks()
        px = root.winfo_x()
        py = root.winfo_y()
        pw = root.winfo_width()
        ph = root.winfo_height()
        dx = px + (pw - 650) // 2
        dy = py + (ph - 520) // 2
        self.dialog.geometry(f"650x520+{max(0, dx)}+{max(0, dy)}")

        root_was_hidden = not root.winfo_viewable()
        if root_was_hidden:
            root.deiconify()
            root.update_idletasks()
            self._root_was_hidden = True

        self.dialog.grab_set()

        self._blocking = load_config() is None
        if self._blocking:
            self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._proc_entries: list[dict] = []
        self._build_ui()
        self._load_current_config()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable process list
        canvas = tk.Canvas(main_frame, height=320, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        self._proc_frame = ttk.Frame(canvas)
        self._proc_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._proc_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Add button
        add_btn = ttk.Button(main_frame, text="Add Process", command=self._add_process)
        add_btn.pack(pady=(5, 0))

        # --- Global settings ---
        global_frame = ttk.LabelFrame(main_frame, text="Global", padding=5)
        global_frame.pack(fill=tk.X, pady=(10, 0))

        output_frame = ttk.Frame(global_frame)
        output_frame.pack(fill=tk.X, pady=2)
        ttk.Label(output_frame, text="Output refresh interval (ms):").pack(side=tk.LEFT)
        self.output_refresh_var = tk.StringVar(value="500")
        ttk.Spinbox(
            output_frame,
            textvariable=self.output_refresh_var,
            from_=100,
            to=5000,
            increment=100,
            width=6,
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(output_frame, text="(lower = smoother, higher = less CPU)").pack(
            side=tk.LEFT, padx=(5, 0)
        )

        self.autostart_var = tk.BooleanVar()
        ttk.Checkbutton(
            global_frame,
            text="Start AIRobotUI with Windows (autostart)",
            variable=self.autostart_var,
        ).pack(anchor=tk.W, pady=2)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        if not self._blocking:
            ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
                side=tk.RIGHT
            )

    def _add_process(self, defaults: dict | None = None) -> None:
        if defaults is None:
            defaults = {
                "name": "",
                "cwd": "",
                "cmd": "",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": "",
                "delete_before_start": "",
            }

        idx = len(self._proc_entries)
        frame = ttk.LabelFrame(self._proc_frame, text=f"Process {idx + 1}", padding=5)
        frame.pack(fill=tk.X, pady=2)

        v: dict[str, tk.Variable] = {}

        # Row 0: Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=1)
        v["name"] = tk.StringVar(value=defaults["name"])
        ttk.Entry(frame, textvariable=v["name"], width=20).grid(
            row=0, column=1, sticky=tk.W, padx=5
        )

        # Row 1: CWD
        ttk.Label(frame, text="CWD:").grid(row=1, column=0, sticky=tk.W, pady=1)
        v["cwd"] = tk.StringVar(value=defaults["cwd"])
        ttk.Entry(frame, textvariable=v["cwd"], width=50).grid(
            row=1, column=1, sticky=tk.EW, padx=5
        )
        ttk.Button(
            frame, text="...", width=3, command=lambda: self._browse_dir(v["cwd"])
        ).grid(row=1, column=2)

        # Row 2: Cmd
        ttk.Label(frame, text="Cmd:").grid(row=2, column=0, sticky=tk.W, pady=1)
        v["cmd"] = tk.StringVar(value=defaults["cmd"])
        ttk.Entry(frame, textvariable=v["cmd"], width=50).grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, padx=5
        )

        # Row 3: Encoding
        ttk.Label(frame, text="Encoding:").grid(row=3, column=0, sticky=tk.W, pady=1)
        v["encoding"] = tk.StringVar(value=defaults["encoding"])
        ttk.Combobox(
            frame,
            textvariable=v["encoding"],
            values=["utf-8", "gbk", "gb2312", "cp936", "shift_jis", "latin-1"],
            width=12,
            state="readonly",
        ).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Row 4: Singleton, Autostart
        check_frame = ttk.Frame(frame)
        check_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=2)
        v["singleton"] = tk.BooleanVar(value=defaults["singleton"])
        ttk.Checkbutton(
            check_frame, text="Singleton", variable=v["singleton"]
        ).pack(side=tk.LEFT, padx=(0, 10))
        v["autostart"] = tk.BooleanVar(value=defaults["autostart"])
        ttk.Checkbutton(
            check_frame, text="Autostart", variable=v["autostart"]
        ).pack(side=tk.LEFT)

        # Row 5: WebUI Pattern
        ttk.Label(frame, text="WebUI Pattern:").grid(
            row=5, column=0, sticky=tk.W, pady=1
        )
        v["webui_pattern"] = tk.StringVar(value=defaults["webui_pattern"])
        ttk.Entry(frame, textvariable=v["webui_pattern"], width=50).grid(
            row=5, column=1, columnspan=2, sticky=tk.EW, padx=5
        )

        # Row 6: Delete before start
        ttk.Label(frame, text="Delete files:").grid(
            row=6, column=0, sticky=tk.W, pady=1
        )
        v["delete_before_start"] = tk.StringVar(value=defaults["delete_before_start"])
        ttk.Entry(frame, textvariable=v["delete_before_start"], width=50).grid(
            row=6, column=1, columnspan=2, sticky=tk.EW, padx=5
        )
        ttk.Label(
            frame, text="(comma-separated, relative to CWD)", foreground="gray"
        ).grid(row=7, column=1, columnspan=2, sticky=tk.W, padx=5)

        # Delete button
        ttk.Button(
            frame,
            text="Delete",
            command=lambda f=frame, idx=idx: self._delete_process(f, idx),
        ).grid(row=8, column=2, sticky=tk.E, pady=(5, 0))

        frame.columnconfigure(1, weight=1)
        self._proc_entries.append({"frame": frame, "vars": v})

    def _delete_process(self, frame: ttk.Frame, idx: int) -> None:
        frame.destroy()
        del self._proc_entries[idx]
        for i, entry in enumerate(self._proc_entries):
            entry["frame"].configure(text=f"Process {i + 1}")

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Select Working Directory")
        if path:
            var.set(path)

    def _load_current_config(self) -> None:
        config = load_config()
        if config is None:
            config = get_default_config()

        for proc in config.get("processes", []):
            self._add_process({
                "name": proc["name"],
                "cwd": proc.get("cwd", ""),
                "cmd": proc.get("cmd", ""),
                "encoding": proc.get("encoding", "utf-8"),
                "singleton": proc.get("singleton", False),
                "autostart": proc.get("autostart", False),
                "webui_pattern": proc.get("webui_pattern") or "",
                "delete_before_start": ", ".join(
                    proc.get("delete_before_start", [])
                ),
            })

        self.output_refresh_var.set(str(config.get("output_refresh_ms", 500)))
        self.autostart_var.set(is_autostart_enabled())

    def _validate(self) -> str | None:
        names: set[str] = set()
        for entry in self._proc_entries:
            v = entry["vars"]
            name = v["name"].get().strip()
            if not name:
                return "Process name cannot be empty."
            if name in names:
                return f"Duplicate process name: {name}"
            names.add(name)
            cwd = v["cwd"].get().strip()
            if cwd and not os.path.exists(cwd):
                return f"CWD not found for '{name}': {cwd}"
            if not v["cmd"].get().strip():
                return f"Command is required for '{name}'."
        return None

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            messagebox.showerror("Validation Error", error, parent=self.dialog)
            return

        processes = []
        for entry in self._proc_entries:
            v = entry["vars"]
            delete_files = [
                f.strip()
                for f in v["delete_before_start"].get().split(",")
                if f.strip()
            ]
            processes.append({
                "name": v["name"].get().strip(),
                "cwd": v["cwd"].get().strip(),
                "cmd": v["cmd"].get().strip(),
                "encoding": v["encoding"].get().strip(),
                "singleton": v["singleton"].get(),
                "autostart": v["autostart"].get(),
                "webui_pattern": v["webui_pattern"].get().strip() or None,
                "delete_before_start": delete_files,
            })

        config = {
            "processes": processes,
            "output_refresh_ms": int(self.output_refresh_var.get()),
            "autostart": self.autostart_var.get(),
        }

        if save_config(config):
            self._logger.info("Config saved via settings dialog")
            if config["autostart"]:
                enable_autostart()
            else:
                disable_autostart()
            self._result = config
            self._on_close()
        else:
            messagebox.showerror(
                "Error", "Failed to save configuration.", parent=self.dialog
            )

    def _on_close(self) -> None:
        if self._root_was_hidden:
            self.dialog.master.withdraw()
        self.dialog.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self._on_close()

    def get_result(self) -> dict | None:
        self.dialog.wait_window()
        return self._result
```

- [ ] **Step 2: Verify module imports**

```bash
uv run python -c "from src.config_ui import ConfigDialog; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/config_ui.py
git commit -m "refactor(config_ui): dynamic scrollable process list editor"
```

---

## Task 8: main.pyw — generic action dispatch + autostart

**Files:**
- Modify: `src/main.pyw`

- [ ] **Step 1: Replace the main function**

Replace the file with the generic version:

```python
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
    POLL_INTERVAL_MS = 2000
    _last_poll = 0

    def _tick() -> None:
        nonlocal _last_poll

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
                                logger.warning(
                                    "Failed to open %s WebUI: %s", name, url
                                )
                        except Exception:
                            logger.warning(
                                "Failed to open %s WebUI: %s",
                                name,
                                url,
                                exc_info=True,
                            )
                    else:
                        pm._system_msg(name, f"{name} WebUI URL not detected yet")

        # 2. Drain output queues to window tabs
        for name in pm.process_names():
            for line in pm.drain(name):
                window.append_output(name, line)

        # 3. Periodic crash poll
        now = time.monotonic() * 1000
        if now - _last_poll >= POLL_INTERVAL_MS:
            _last_poll = now
            pm.poll_crashes()

        # 4. Exit check
        if tray._exit_requested:
            logger.info("Exit: hiding window, shutting down...")
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
```

- [ ] **Step 2: Verify the file parses**

```bash
uv run python -c "import ast; ast.parse(open('src/main.pyw').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add src/main.pyw
git commit -m "refactor(main): generic action dispatch + per-process autostart"
```

---

## Task 9: Final verification

**Files:**
- All files modified in Tasks 1-8

- [ ] **Step 1: Check all modules import without errors**

```bash
uv run python -c "
from src.icon import save_ico
from src.logger import get_process_logger, get_napcat_logger, get_astrbot_logger
from src.config import load_config, save_config, get_default_config
from src.process_mgr import ProcessManager
from src.main_window import MainWindow
from src.tray_ui import TrayUI
from src.config_ui import ConfigDialog
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 2: Test config migration (unit test)**

```bash
uv run python -c "
import json, os, sys, shutil
sys.path.insert(0, 'src')

# Point data dir to temp location
test_dir = os.path.join(os.getcwd(), '_test_migration')
os.environ['LOCALAPPDATA'] = test_dir
from config import get_data_dir, load_config, save_config, get_default_config
data_dir = get_data_dir()
os.makedirs(data_dir, exist_ok=True)

# Write old-format config
old = {
    'napcat': {'cwd': 'X:\\napcat', 'cmd': 'napcat.exe', 'encoding': 'utf-8'},
    'astrbot': {'cwd': 'X:\\astrbot', 'cmd': 'astrbot run', 'encoding': 'utf-8'},
    'output_refresh_ms': 300,
    'autostart': True,
}
with open(os.path.join(data_dir, 'config.json'), 'w') as f:
    json.dump(old, f)

cfg = load_config()
assert 'processes' in cfg, 'Missing processes key'
assert len(cfg['processes']) == 2, f'Expected 2 processes, got {len(cfg[\"processes\"])}'
assert cfg['processes'][0]['name'] == 'NapCat'
assert cfg['processes'][1]['name'] == 'AstrBot'
assert cfg['processes'][1]['delete_before_start'] == ['astrbot.lock']
assert cfg['output_refresh_ms'] == 300
assert cfg['autostart'] == True

# Verify file was saved in new format
with open(os.path.join(data_dir, 'config.json'), 'r') as f:
    saved = json.load(f)
assert 'processes' in saved

shutil.rmtree(test_dir, ignore_errors=True)
print('Migration test PASSED')
"
```
Expected: `Migration test PASSED`

- [ ] **Step 3: Test ProcessManager start/stop/drain API (unit test)**

```bash
uv run python -c "
import sys, time
sys.path.insert(0, 'src')
from process_mgr import ProcessManager

config = {
    'processes': [
        {
            'name': 'TestProc',
            'cwd': '',
            'cmd': sys.executable + ' -c \"import time; time.sleep(5)\"',
            'encoding': 'utf-8',
            'singleton': False,
            'autostart': False,
            'webui_pattern': None,
            'delete_before_start': [],
        }
    ],
    'output_refresh_ms': 500,
    'autostart': False,
}

pm = ProcessManager(config)
assert pm.process_names() == ['TestProc']
assert not pm.is_running('TestProc')
assert not pm.has_webui('TestProc')

pm.start('TestProc')
time.sleep(0.5)
assert pm.is_running('TestProc'), 'Process should be running'

lines = pm.drain('TestProc')
assert len(lines) >= 0, 'Drain should return list'

pm.stop('TestProc')
time.sleep(0.5)
assert not pm.is_running('TestProc'), 'Process should be stopped'

print('ProcessManager API test PASSED')
"
```
Expected: `ProcessManager API test PASSED`

- [ ] **Step 4: Run ruff format and check**

```bash
uv run ruff format src/ && uv run ruff check src/
```
Expected: No errors

- [ ] **Step 5: Commit final verification changes**

```bash
git add -A && git diff --cached --stat
```
If any formatting changes, commit them.

---

## Plan Complete

All 9 tasks cover the full spec:
- Task 1-2: Foundation (icon, logger) — no dependencies
- Task 3: Config schema + migration — depends on nothing
- Task 4: ProcessManager refactor — depends on config schema, logger
- Task 5: MainWindow dynamic tabs + taskbar — depends on icon, config (get_data_dir)
- Task 6: TrayUI dynamic menus — depends on ProcessManager API
- Task 7: ConfigDialog dynamic editor — depends on config, startup
- Task 8: main.pyw generic dispatch — depends on all of the above
- Task 9: Verification

Each task produces a working, importable module. The app only becomes fully functional after Task 8 (which ties everything together).
