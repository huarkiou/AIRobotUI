# AIRobotUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows system tray app that controls NapCat QQ and AstrBot processes with configurable paths, autostart, real-time output display, and logging.

**Architecture:** Bottom-up: logger → config → icon → startup → process_mgr → main_window → config_ui → tray_ui → main integration. Each module has a single responsibility, communicates via callbacks and method calls.

**Tech Stack:** Python 3.11+, tkinter (built-in), pystray, Pillow, PyInstaller, winreg (built-in)

---

### Task 1: Project Initialization

**Files:**
- Create: `pyproject.toml`
- Create: `airobotui.bat`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "airobotui"
version = "0.1.0"
description = "Windows system tray controller for NapCat QQ and AstrBot"
requires-python = ">=3.11"
dependencies = [
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
    "pyinstaller>=6.0.0",
]

[tool.pyright]
typeCheckingMode = "basic"
```

- [ ] **Step 2: Create airobotui.bat**

```bat
@echo off
chcp 65001 >nul
uv run python main.pyw
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
dist/
build/
*.spec
*.egg-info/
.venv/
.env
```

- [ ] **Step 4: Initialize git and install dependencies**

```bash
git init
git add pyproject.toml airobotui.bat .gitignore
git commit -m "chore: project initialization"
uv sync
```

---

### Task 2: Logger Module

**Files:**
- Create: `logger.py`

- [ ] **Step 1: Create logger.py**

```python
"""Logging module for AIRobotUI - writes to %LOCALAPPDATA%\AIRobotUI\logs\"""

import logging
import os
from logging.handlers import RotatingFileHandler


def _get_log_dir() -> str:
    """Get or create the log directory under LOCALAPPDATA."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(local_appdata, "AIRobotUI", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _create_logger(name: str, filename: str) -> logging.Logger:
    """Create a logger with rotating file handler."""
    log_dir = _get_log_dir()
    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=1 * 1024 * 1024,  # 1 MB
            backupCount=3,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Module-level singletons
_main_logger = None
_napcat_logger = None
_astrbot_logger = None


def get_main_logger() -> logging.Logger:
    global _main_logger
    if _main_logger is None:
        _main_logger = _create_logger("airobotui.main", "airobotui.log")
    return _main_logger


def get_napcat_logger() -> logging.Logger:
    global _napcat_logger
    if _napcat_logger is None:
        _napcat_logger = _create_logger("airobotui.napcat", "napcat.log")
    return _napcat_logger


def get_astrbot_logger() -> logging.Logger:
    global _astrbot_logger
    if _astrbot_logger is None:
        _astrbot_logger = _create_logger("airobotui.astrbot", "astrbot.log")
    return _astrbot_logger
```

- [ ] **Step 2: Verify logger works**

```bash
uv run python -c "from logger import get_main_logger; l = get_main_logger(); l.info('test ok'); print('PASS')"
```
Expected: "PASS" printed, log file created at `%LOCALAPPDATA%\AIRobotUI\logs\airobotui.log`

- [ ] **Step 3: Commit**

```bash
git add logger.py
git commit -m "feat: add logging module with rotating file handlers"
```

---

### Task 3: Config Module

**Files:**
- Create: `config.py`

- [ ] **Step 1: Create config.py**

```python
"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\AIRobotUI\"""

import json
import os
from logger import get_main_logger


def get_data_dir() -> str:
    """Get or create the data directory under LOCALAPPDATA."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    data_dir = os.path.join(local_appdata, "AIRobotUI")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_config_path() -> str:
    return os.path.join(get_data_dir(), "config.json")


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "napcat": {
            "cwd": "D:\\Apps\\ai\\napcatqq\\NapCat.44498.Shell",
            "cmd": "napcat.quick.bat",
        },
        "astrbot": {
            "cwd": "D:\\Apps\\ai\\astrbot",
            "cmd": "astrbot run",
        },
        "autostart": False,
    }


def load_config() -> dict | None:
    """Load config from file. Returns None if file does not exist."""
    logger = get_main_logger()
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        logger.info("Config file not found at %s", config_path)
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info("Config loaded from %s", config_path)
        return config
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load config: %s", e)
        return None


def save_config(config: dict) -> bool:
    """Save config to file. Returns True on success."""
    logger = get_main_logger()
    config_path = _get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Config saved to %s", config_path)
        return True
    except IOError as e:
        logger.error("Failed to save config: %s", e)
        return False
```

- [ ] **Step 2: Verify config module**

```bash
uv run python -c "
from config import load_config, save_config, get_default_config
cfg = get_default_config()
assert save_config(cfg) == True
loaded = load_config()
assert loaded == cfg
# Test missing file
import os, config
path = config._get_config_path()
os.remove(path)
assert load_config() is None
print('PASS')
"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat: add config module with JSON persistence to LOCALAPPDATA"
```

---

### Task 4: Icon Generator

**Files:**
- Create: `icon.py`

- [ ] **Step 1: Create icon.py**

```python
"""Dynamic tray icon generation using Pillow."""

from PIL import Image, ImageDraw


ICON_SIZE = 64


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    """Generate a solid-color circle icon."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=color,
    )
    return img


GREEN = (76, 175, 80)
YELLOW = (255, 193, 7)
RED = (244, 67, 54)


def get_green_icon() -> Image.Image:
    return _make_icon(GREEN)


def get_yellow_icon() -> Image.Image:
    return _make_icon(YELLOW)


def get_red_icon() -> Image.Image:
    return _make_icon(RED)
```

- [ ] **Step 2: Verify icon generation**

```bash
uv run python -c "
from icon import get_green_icon, get_yellow_icon, get_red_icon
g = get_green_icon()
assert g.size == (64, 64)
assert g.mode == 'RGBA'
print('PASS')
"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add icon.py
git commit -m "feat: add dynamic tray icon generator (green/yellow/red)"
```

---

### Task 5: Autostart Module

**Files:**
- Create: `startup.py`

- [ ] **Step 1: Create startup.py**

```python
"""Windows autostart management via registry."""

import sys
import os
import winreg
from logger import get_main_logger

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "AIRobotUI"


def _get_exe_path() -> str:
    """Get the path to use for autostart entry."""
    if getattr(sys, "frozen", False):
        # Running as compiled EXE
        return sys.executable
    else:
        # Running from source - use batch file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bat_path = os.path.join(script_dir, "airobotui.bat")
        if os.path.exists(bat_path):
            return bat_path
        return sys.executable


def is_autostart_enabled() -> bool:
    """Check if autostart registry entry exists."""
    logger = get_main_logger()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, REG_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.error("Failed to read autostart registry: %s", e)
        return False


def enable_autostart() -> bool:
    """Create autostart registry entry. Returns True on success."""
    logger = get_main_logger()
    exe_path = _get_exe_path()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, exe_path)
        logger.info("Autostart enabled: %s", exe_path)
        return True
    except OSError as e:
        logger.error("Failed to enable autostart: %s", e)
        return False


def disable_autostart() -> bool:
    """Remove autostart registry entry. Returns True on success."""
    logger = get_main_logger()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, REG_VALUE_NAME)
        logger.info("Autostart disabled")
        return True
    except FileNotFoundError:
        return True  # Already not present
    except OSError as e:
        logger.error("Failed to disable autostart: %s", e)
        return False
```

- [ ] **Step 2: Verify startup module**

```bash
uv run python -c "
from startup import is_autostart_enabled, enable_autostart, disable_autostart
assert disable_autostart() == True
assert is_autostart_enabled() == False
assert enable_autostart() == True
assert is_autostart_enabled() == True
assert disable_autostart() == True
print('PASS')
"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add startup.py
git commit -m "feat: add autostart module via Windows registry"
```

---

### Task 6: Process Manager

**Files:**
- Create: `process_mgr.py`

- [ ] **Step 1: Create process_mgr.py**

```python
"""Process manager for NapCat QQ and AstrBot - lifecycle, monitoring, output capture."""

import subprocess
import threading
import time
import shlex
from typing import Callable
from logger import get_main_logger, get_napcat_logger, get_astrbot_logger


StatusCallback = Callable[[], None]
OutputCallback = Callable[[str, str], None]  # (process_name, line)


class ProcessManager:
    def __init__(self, config: dict):
        self._config = config
        self._napcat_proc: subprocess.Popen | None = None
        self._astrbot_proc: subprocess.Popen | None = None
        self._napcat_restart_count = 0
        self._astrbot_restart_count = 0
        self._max_restarts = 3
        self._monitor_running = False
        self._monitor_thread: threading.Thread | None = None
        self._output_callbacks: list[OutputCallback] = []
        self._status_callbacks: list[StatusCallback] = []
        self._lock = threading.Lock()

    # --- Public API ---

    def update_config(self, config: dict) -> None:
        """Update config without stopping running processes."""
        self._config = config

    def on_status_change(self, callback: StatusCallback) -> None:
        self._status_callbacks.append(callback)

    def on_output(self, callback: OutputCallback) -> None:
        self._output_callbacks.append(callback)

    def start_all(self) -> None:
        self.start_napcat()
        self.start_astrbot()

    def stop_all(self) -> None:
        self.stop_napcat()
        self.stop_astrbot()

    def start_napcat(self) -> None:
        self._start_process("napcat")

    def start_astrbot(self) -> None:
        self._start_process("astrbot")

    def stop_napcat(self) -> None:
        self._stop_process("napcat")

    def stop_astrbot(self) -> None:
        self._stop_process("astrbot")

    def is_napcat_running(self) -> bool:
        return self._is_running("napcat")

    def is_astrbot_running(self) -> bool:
        return self._is_running("astrbot")

    def start_monitor(self) -> None:
        """Start the background monitor thread."""
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def stop_monitor(self) -> None:
        """Stop the background monitor thread."""
        self._monitor_running = False

    # --- Internal ---

    def _proc_name(self, name: str) -> str:
        return "NapCat" if name == "napcat" else "AstrBot"

    def _proc_config(self, name: str) -> dict:
        return self._config[name]

    def _proc_attr(self, name: str) -> str:
        return "_napcat_proc" if name == "napcat" else "_astrbot_proc"

    def _restart_count_attr(self, name: str) -> str:
        return "_napcat_restart_count" if name == "napcat" else "_astrbot_restart_count"

    def _get_proc(self, name: str) -> subprocess.Popen | None:
        return getattr(self, self._proc_attr(name))

    def _set_proc(self, name: str, proc: subprocess.Popen | None) -> None:
        setattr(self, self._proc_attr(name), proc)

    def _get_restart_count(self, name: str) -> int:
        return getattr(self, self._restart_count_attr(name))

    def _set_restart_count(self, name: str, value: int) -> None:
        setattr(self, self._restart_count_attr(name), value)

    def _is_running(self, name: str) -> bool:
        proc = self._get_proc(name)
        return proc is not None and proc.poll() is None

    def _get_logger(self, name: str) -> "logging.Logger":
        if name == "napcat":
            return get_napcat_logger()
        return get_astrbot_logger()

    def _notify_status(self) -> None:
        for cb in self._status_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _notify_output(self, name: str, line: str) -> None:
        proc_name = self._proc_name(name)
        for cb in self._output_callbacks:
            try:
                cb(proc_name, line)
            except Exception:
                pass

    def _read_output(self, pipe, name: str) -> None:
        """Read lines from a process pipe in a dedicated thread."""
        proc_logger = self._get_logger(name)
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                line = line.rstrip("\n\r")
                if line:
                    proc_logger.info(line)
                    self._notify_output(name, line)
        except (ValueError, IOError):
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _start_process(self, name: str) -> None:
        logger = get_main_logger()
        proc_name = self._proc_name(name)

        if self._is_running(name):
            logger.info("%s is already running", proc_name)
            return

        proc_config = self._proc_config(name)
        cwd = proc_config["cwd"]
        cmd = proc_config["cmd"]

        if not os.path.exists(cwd):
            logger.error("%s: working directory not found: %s", proc_name, cwd)
            self._notify_output(name, f"[ERROR] Working directory not found: {cwd}")
            return

        logger.info("Starting %s: cwd=%s cmd=%s", proc_name, cwd, cmd)

        try:
            # Use shell=True only for .bat files
            use_shell = cmd.endswith(".bat") or cmd.endswith(".cmd")
            if use_shell:
                args = cmd
            else:
                args = shlex.split(cmd)

            proc = subprocess.Popen(
                args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=use_shell,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._set_proc(name, proc)
            self._set_restart_count(name, 0)

            # Start output reader thread
            reader = threading.Thread(
                target=self._read_output,
                args=(proc.stdout, name),
                daemon=True,
            )
            reader.start()

            logger.info("%s started (PID: %d)", proc_name, proc.pid)
            self._notify_status()

            # Start monitor if not already running
            self.start_monitor()

        except FileNotFoundError:
            logger.error("%s: executable not found: %s", proc_name, cmd)
            self._notify_output(name, f"[ERROR] Executable not found: {cmd}")
        except Exception as e:
            logger.error("%s: failed to start: %s", proc_name, e)
            self._notify_output(name, f"[ERROR] Failed to start: {e}")

    def _stop_process(self, name: str) -> None:
        logger = get_main_logger()
        proc_name = self._proc_name(name)
        proc = self._get_proc(name)

        if proc is None:
            logger.info("%s is not running", proc_name)
            return

        logger.info("Stopping %s (PID: %d)...", proc_name, proc.pid)
        self._set_restart_count(name, self._max_restarts)  # Prevent auto-restart

        try:
            proc.terminate()
        except Exception:
            pass

        try:
            proc.wait(timeout=3)
            logger.info("%s stopped gracefully", proc_name)
        except subprocess.TimeoutExpired:
            logger.warning("%s did not stop, force killing", proc_name)
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass

        self._set_proc(name, None)
        self._notify_output(name, f"[SYSTEM] {proc_name} stopped")
        self._notify_status()

    def _monitor_loop(self) -> None:
        """Background thread: poll process status every 2 seconds."""
        logger = get_main_logger()
        while self._monitor_running:
            for name in ("napcat", "astrbot"):
                proc = self._get_proc(name)
                if proc is None:
                    continue

                ret = proc.poll()
                if ret is not None:
                    proc_name = self._proc_name(name)
                    count = self._get_restart_count(name)
                    logger.warning(
                        "%s exited with code %d (restart count: %d/%d)",
                        proc_name, ret, count, self._max_restarts,
                    )
                    self._notify_output(
                        name,
                        f"[SYSTEM] {proc_name} exited with code {ret}",
                    )
                    self._set_proc(name, None)
                    self._notify_status()

                    if count < self._max_restarts:
                        self._set_restart_count(name, count + 1)
                        logger.info("Auto-restarting %s...", proc_name)
                        self._notify_output(
                            name,
                            f"[SYSTEM] Auto-restarting {proc_name} ({count + 1}/{self._max_restarts})...",
                        )
                        self._start_process(name)
                    else:
                        logger.error(
                            "%s: max restarts (%d) reached, giving up",
                            proc_name, self._max_restarts,
                        )
                        self._notify_output(
                            name,
                            f"[SYSTEM] {proc_name}: max restarts reached, giving up",
                        )

            time.sleep(2)

    def shutdown(self) -> None:
        """Stop all processes and monitor."""
        logger = get_main_logger()
        logger.info("Shutting down...")
        self.stop_monitor()
        self.stop_all()
        logger.info("Shutdown complete")


# Import at bottom to avoid circular dependency
import os
import logging
```

- [ ] **Step 2: Verify process_mgr import**

```bash
uv run python -c "from process_mgr import ProcessManager; print('PASS')"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add process_mgr.py
git commit -m "feat: add process manager with lifecycle, monitoring, and output capture"
```

---

### Task 7: Main Window (Output Panel)

**Files:**
- Create: `main_window.py`

- [ ] **Step 1: Create main_window.py**

```python
"""Main window with two-tab output display for NapCat and AstrBot."""

import tkinter as tk
from tkinter import ttk
from logger import get_main_logger

MAX_LINES = 5000


class MainWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AIRobotUI - Process Control")
        self.root.geometry("800x500")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # NapCat tab
        self.napcat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.napcat_frame, text="NapCat")
        self.napcat_text = self._create_text_widget(self.napcat_frame)

        # AstrBot tab
        self.astrbot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.astrbot_frame, text="AstrBot")
        self.astrbot_text = self._create_text_widget(self.astrbot_frame)

        self._visible = False
        self._close_callback: callable | None = None
        self._logger = get_main_logger()

    def _create_text_widget(self, parent: ttk.Frame) -> tk.Text:
        """Create a terminal-style read-only text widget."""
        frame = tk.Frame(parent, bg="black")
        frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            frame,
            bg="black",
            fg="#00FF00",
            insertbackground="#00FF00",
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
        )
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        # Right-click context menu
        context_menu = tk.Menu(text, tearoff=0)
        context_menu.add_command(
            label="Clear", command=lambda: self._clear_tab(text)
        )
        context_menu.add_command(
            label="Copy", command=lambda: self._copy_selection(text)
        )
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
            pass  # No selection

    def set_on_close(self, callback: callable) -> None:
        """Set callback for when user closes the window."""
        self._close_callback = callback

    def _on_close(self) -> None:
        """Hide window instead of closing."""
        self.root.withdraw()
        self._visible = False
        self._logger.info("Main window hidden")
        if self._close_callback:
            self._close_callback()

    def show(self) -> None:
        """Show and focus the window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._visible = True
        self._logger.info("Main window shown")

    def hide(self) -> None:
        """Hide the window."""
        self.root.withdraw()
        self._visible = False

    def toggle(self) -> None:
        """Toggle window visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        return self._visible

    def append_output(self, process_name: str, line: str) -> None:
        """Append a line to the appropriate tab. Thread-safe via root.after."""
        self.root.after(0, self._append_output_impl, process_name, line)

    def _append_output_impl(self, process_name: str, line: str) -> None:
        """Actually append the output line (must run on main thread)."""
        if process_name == "NapCat":
            text = self.napcat_text
        elif process_name == "AstrBot":
            text = self.astrbot_text
        else:
            return

        text.config(state=tk.NORMAL)
        text.insert(tk.END, line + "\n")

        # Enforce line limit
        line_count = int(text.index("end-1c").split(".")[0])
        if line_count > MAX_LINES:
            excess = line_count - MAX_LINES
            text.delete("1.0", f"{excess}.0")

        text.config(state=tk.DISABLED)
        text.see(tk.END)

    def destroy(self) -> None:
        """Destroy the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        """Start the tkinter main loop (should NOT be called - pystray handles it)."""
        # Window is created but mainloop is managed elsewhere
        pass
```

- [ ] **Step 2: Verify main_window import**

```bash
uv run python -c "from main_window import MainWindow; print('PASS')"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add main_window.py
git commit -m "feat: add main window with dual-tab terminal-style output panel"
```

---

### Task 8: Config UI

**Files:**
- Create: `config_ui.py`

- [ ] **Step 1: Create config_ui.py**

```python
"""Configuration dialog for AIRobotUI."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from config import load_config, save_config, get_default_config
from startup import enable_autostart, disable_autostart, is_autostart_enabled
from logger import get_main_logger


class ConfigDialog:
    def __init__(self, root: tk.Tk) -> None:
        self._logger = get_main_logger()
        self._result: dict | None = None

        self.dialog = tk.Toplevel(root)
        self.dialog.title("AIRobotUI - Settings")
        self.dialog.geometry("550x320")
        self.dialog.resizable(False, False)
        self.dialog.transient(root)
        self.dialog.grab_set()

        # Prevent closing if no config exists
        self._blocking = load_config() is None
        if self._blocking:
            self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        self._build_ui()
        self._load_current_config()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- NapCat ---
        napcat_frame = ttk.LabelFrame(main_frame, text="NapCat QQ", padding=5)
        napcat_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(napcat_frame, text="Working Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self.napcat_cwd = tk.StringVar()
        ttk.Entry(napcat_frame, textvariable=self.napcat_cwd, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(5, 2)
        )
        ttk.Button(
            napcat_frame, text="Browse...",
            command=lambda: self._browse_dir(self.napcat_cwd),
        ).grid(row=0, column=2)

        ttk.Label(napcat_frame, text="Command:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        self.napcat_cmd = tk.StringVar()
        ttk.Entry(napcat_frame, textvariable=self.napcat_cmd, width=40).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(5, 0)
        )

        napcat_frame.columnconfigure(1, weight=1)

        # --- AstrBot ---
        astrbot_frame = ttk.LabelFrame(main_frame, text="AstrBot", padding=5)
        astrbot_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(astrbot_frame, text="Working Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self.astrbot_cwd = tk.StringVar()
        ttk.Entry(astrbot_frame, textvariable=self.astrbot_cwd, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(5, 2)
        )
        ttk.Button(
            astrbot_frame, text="Browse...",
            command=lambda: self._browse_dir(self.astrbot_cwd),
        ).grid(row=0, column=2)

        ttk.Label(astrbot_frame, text="Command:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        self.astrbot_cmd = tk.StringVar()
        ttk.Entry(astrbot_frame, textvariable=self.astrbot_cmd, width=40).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(5, 0)
        )

        astrbot_frame.columnconfigure(1, weight=1)

        # --- Autostart ---
        autostart_frame = ttk.Frame(main_frame)
        autostart_frame.pack(fill=tk.X, pady=(0, 10))
        self.autostart_var = tk.BooleanVar()
        ttk.Checkbutton(
            autostart_frame,
            text="Start with Windows (autostart)",
            variable=self.autostart_var,
        ).pack(anchor=tk.W)

        # --- Buttons ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        if not self._blocking:
            ttk.Button(
                btn_frame, text="Cancel", command=self._on_cancel
            ).pack(side=tk.RIGHT)

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Select Working Directory")
        if path:
            var.set(path)

    def _load_current_config(self) -> None:
        config = load_config()
        if config is None:
            config = get_default_config()

        self.napcat_cwd.set(config["napcat"]["cwd"])
        self.napcat_cmd.set(config["napcat"]["cmd"])
        self.astrbot_cwd.set(config["astrbot"]["cwd"])
        self.astrbot_cmd.set(config["astrbot"]["cmd"])
        self.autostart_var.set(is_autostart_enabled())

    def _validate(self) -> str | None:
        """Validate inputs. Returns error string or None if valid."""
        import os
        if not self.napcat_cwd.get().strip():
            return "NapCat working directory is required."
        if not self.napcat_cmd.get().strip():
            return "NapCat command is required."
        if not self.astrbot_cwd.get().strip():
            return "AstrBot working directory is required."
        if not self.astrbot_cmd.get().strip():
            return "AstrBot command is required."
        if not os.path.exists(self.napcat_cwd.get().strip()):
            return f"NapCat directory does not exist:\n{self.napcat_cwd.get()}"
        if not os.path.exists(self.astrbot_cwd.get().strip()):
            return f"AstrBot directory does not exist:\n{self.astrbot_cwd.get()}"
        return None

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            messagebox.showerror("Validation Error", error, parent=self.dialog)
            return

        config = {
            "napcat": {
                "cwd": self.napcat_cwd.get().strip(),
                "cmd": self.napcat_cmd.get().strip(),
            },
            "astrbot": {
                "cwd": self.astrbot_cwd.get().strip(),
                "cmd": self.astrbot_cmd.get().strip(),
            },
            "autostart": self.autostart_var.get(),
        }

        if save_config(config):
            self._logger.info("Config saved via settings dialog")

            # Handle autostart
            if config["autostart"]:
                enable_autostart()
            else:
                disable_autostart()

            self._result = config
            self.dialog.destroy()
        else:
            messagebox.showerror(
                "Error", "Failed to save configuration.", parent=self.dialog
            )

    def _on_cancel(self) -> None:
        self._result = None
        self.dialog.destroy()

    def get_result(self) -> dict | None:
        """Wait for dialog and return config dict, or None if cancelled."""
        self.dialog.wait_window()
        return self._result


import os  # used in _validate
```

- [ ] **Step 2: Verify config_ui import**

```bash
uv run python -c "from config_ui import ConfigDialog; print('PASS')"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add config_ui.py
git commit -m "feat: add config dialog with browse, validation, and autostart toggle"
```

---

### Task 9: System Tray UI

**Files:**
- Create: `tray_ui.py`

- [ ] **Step 1: Create tray_ui.py**

```python
"""System tray icon and menu for AIRobotUI."""

import threading
import pystray
from pystray import Menu, MenuItem
from icon import get_green_icon, get_yellow_icon, get_red_icon
from logger import get_main_logger


class TrayUI:
    def __init__(
        self,
        process_mgr: "ProcessManager",
        main_window: "MainWindow",
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
        label = "NapCat" if name == "napcat" else "AstrBot"

        def _toggle(icon, item):
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
            self._refresh_icon()

        def _status_text(_):
            if name == "napcat":
                running = self._pm.is_napcat_running()
            else:
                running = self._pm.is_astrbot_running()
            indicator = "\u25CF" if running else "\u25CB"  # ● or ○
            status = "Running" if running else "Stopped"
            return f"{label}    {indicator} {status}"

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

    # --- Actions ---

    def _on_start_all(self, icon, item) -> None:
        self._pm.start_all()

    def _on_stop_all(self, icon, item) -> None:
        self._pm.stop_all()

    def _on_show_window(self, icon, item) -> None:
        self._window.show()

    def _on_settings(self, icon, item) -> None:
        if self._config_callback:
            self._config_callback()

    def _on_exit(self, icon, item) -> None:
        self._logger.info("Exit requested from tray menu")
        self._pm.shutdown()
        self._window.destroy()
        self._icon.stop()

    # --- Lifecycle ---

    def run(self) -> None:
        """Start the tray icon event loop (blocking)."""
        self._logger.info("Starting tray icon")
        # Make left-click toggle the window
        self._icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        self._icon.stop()

    def notify(self, title: str, message: str) -> None:
        """Show a tray notification."""
        try:
            self._icon.notify(message, title)
        except Exception:
            pass


# Lazy imports for type hints
from process_mgr import ProcessManager
from main_window import MainWindow
```

- [ ] **Step 2: Verify tray_ui import**

```bash
uv run python -c "from tray_ui import TrayUI; print('PASS')"
```
Expected: "PASS"

- [ ] **Step 3: Commit**

```bash
git add tray_ui.py
git commit -m "feat: add system tray UI with status menu and process control"
```

---

### Task 10: Main Entry Point

**Files:**
- Create: `main.pyw`

- [ ] **Step 1: Create main.pyw**

```python
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
        logger.info("No config found, showing settings dialog...")
        default_cfg = get_default_config()
        save_config(default_cfg)
        config = default_cfg
        # Show config dialog (blocking)
        dialog = ConfigDialog(window.root)
        result = dialog.get_result()
        if result is not None:
            config = result

    # Step 3: Initialize process manager
    pm = ProcessManager(config)

    # Step 4: Wire output to main window
    pm.on_output(window.append_output)

    # Step 5: Create tray UI
    tray = TrayUI(pm, window, config)

    # Step 6: Settings callback
    def open_settings() -> None:
        logger.info("Opening settings dialog")
        dialog = ConfigDialog(window.root)
        result = dialog.get_result()
        if result is not None:
            pm.update_config(result)
            logger.info("Config updated at runtime")

    tray.set_config_callback(open_settings)

    # Step 7: Window close → hide to tray
    window.set_on_close(lambda: None)  # Already handled by _on_close

    # Step 8: Start tray (blocking)
    logger.info("Entering tray event loop")
    tray.run()

    logger.info("AIRobotUI exited")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.pyw
git commit -m "feat: add main entry point wiring all modules together"
```

---

### Task 11: Build Script

**Files:**
- Create: `build.bat`

- [ ] **Step 1: Create build.bat**

```bat
@echo off
chcp 65001 >nul
echo Building AIRobotUI...
uv run pyinstaller --onefile --windowed --clean --name AIRobotUI main.pyw
echo.
if exist "dist\AIRobotUI.exe" (
    echo Build successful: dist\AIRobotUI.exe
) else (
    echo Build FAILED - check output above
)
pause
```

- [ ] **Step 2: Test build**

```bash
uv run pyinstaller --onefile --windowed --clean --name AIRobotUI main.pyw
```
Verify `dist\AIRobotUI.exe` is created.

- [ ] **Step 3: Commit**

```bash
git add build.bat
# Add .spec files to .gitignore if needed
echo "*.spec" >> .gitignore
git add .gitignore
git commit -m "chore: add PyInstaller build script"
```

---

### Task 12: End-to-End Test

- [ ] **Step 1: Run the application**

```bash
uv run python main.pyw
```

Verify:
1. First run: config dialog pops up automatically
2. Tray icon appears (red initially)
3. Right-click menu shows all items
4. Click "NapCat" to start - icon turns yellow
5. Click "AstrBot" to start - icon turns green
6. "Show Window" opens output panel with dual tabs
7. Process output appears in real-time
8. Closing window hides to tray (does not exit)
9. Stop processes, verify icon turns red
10. Exit cleans up all processes

- [ ] **Step 2: Verify log files**

Check `%LOCALAPPDATA%\AIRobotUI\logs\` for:
- `airobotui.log` - contains start/stop events
- `napcat.log` - contains NapCat output
- `astrbot.log` - contains AstrBot output

- [ ] **Step 3: Verify autostart**

1. Open Settings, enable "Start with Windows"
2. Check registry: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\AIRobotUI` exists
3. Disable, verify entry is removed

- [ ] **Step 4: Commit any fixes**

If bugs found during E2E test, fix them and commit. Then final:

```bash
git add -A
git commit -m "test: end-to-end verification and fixes"
```
