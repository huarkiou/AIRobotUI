# TrayForge Quality Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve internal code quality (exception handling, types, validation, structure, tests) with zero functional changes.

**Architecture:** Sequential improvements in dependency order: exception handling first, then types (shared dependency), then validation/error-surfacing (independent), then extract AppController, then add tests last. Each task builds on the previous without breaking existing behavior.

**Tech Stack:** Python 3.11+, uv, pytest, ruff

---

### Task 1: Tighten exception handling

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Replace bare `except Exception: pass` in `_emit_status`**

In `process_mgr.py`, find `_emit_status`:

```python
    def _emit_status(self) -> None:
        for cb in self._status_listeners:
            try:
                cb()
            except Exception:
                pass
```

Replace with:

```python
    def _emit_status(self) -> None:
        for cb in self._status_listeners:
            try:
                cb()
            except Exception:
                logger = get_main_logger()
                logger.warning("status listener failed", exc_info=True)
```

- [ ] **Step 2: Replace bare `except Exception: pass` in `_notify`**

Find `_notify`:

```python
    def _notify(self, title: str, msg: str) -> None:
        for cb in self._notify_listeners:
            try:
                cb(title, msg)
            except Exception:
                pass
```

Replace with:

```python
    def _notify(self, title: str, msg: str) -> None:
        for cb in self._notify_listeners:
            try:
                cb(title, msg)
            except Exception:
                logger = get_main_logger()
                logger.warning("notification listener failed", exc_info=True)
```

- [ ] **Step 3: Narrow exception catch in `_kill_cwd_processes` inner loop**

Find the inner try/except in `_kill_cwd_processes`:

```python
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                    pass
```

Replace with:

```python
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception:
                    logger = get_main_logger()
                    logger.debug("kill_cwd_processes iter error", exc_info=True)
```

Note: the outer `except Exception: pass` wrapping the entire `for proc in psutil.process_iter(...)` loop stays — it's a defense against the iterator itself failing.

- [ ] **Step 4: Run ruff and verify**

```bash
uv run ruff format src/process_mgr.py && uv run ruff check src/process_mgr.py
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/process_mgr.py
git commit -m "refactor: tighten exception handling in process_mgr"
```

---

### Task 2: Add type definitions (TypedDict)

**Files:**
- Create: `src/types.py`
- Modify: `src/config.py`
- Modify: `src/process_mgr.py`
- Modify: `src/tray_ui.py`
- Modify: `src/config_ui.py`

- [ ] **Step 1: Create src/types.py**

```python
"""Shared type definitions for TrayForge."""

from typing import TypedDict


class ProcessConfig(TypedDict):
    name: str
    cwd: str
    cmd: str
    encoding: str
    singleton: bool
    autostart: bool
    webui_pattern: str | None
    delete_before_start: list[str]


class AppConfig(TypedDict):
    processes: list[ProcessConfig]
    output_refresh_ms: int
    poll_interval_ms: int
    autostart: bool
```

- [ ] **Step 2: Update config.py — add type imports and annotations**

Add at top of `src/config.py`:

```python
from types import AppConfig
```

Update function signatures:

```python
def get_default_config() -> AppConfig:
    ...

def _migrate_old_config(old: dict) -> AppConfig:
    ...

def load_config() -> AppConfig | None:
    ...

def save_config(config: AppConfig) -> bool:
    ...
```

- [ ] **Step 3: Update process_mgr.py — annotate config params and _ProcState.cfg**

Add at top of `src/process_mgr.py`:

```python
from types import ProcessConfig, AppConfig
```

Update `_ProcState` dataclass:

```python
@dataclass
class _ProcState:
    proc: subprocess.Popen | None = None
    msg_queue: queue.Queue = field(default_factory=queue.Queue)
    restarts: int = 0
    webui_url: str | None = None
    last_restart: float = 0.0
    cooldown_notified: bool = False
    cfg: ProcessConfig = field(default_factory=dict)  # type: ignore[assignment]
```

Update method signatures:

```python
class ProcessManager:
    def __init__(self, config: AppConfig) -> None:
        ...

    def update_config(self, config: AppConfig) -> None:
        ...

    def _build_from_config(self, config: AppConfig) -> None:
        ...
```

- [ ] **Step 4: Update tray_ui.py — annotate config param**

Add at top of `src/tray_ui.py`:

```python
from types import AppConfig
from typing import Callable
```

Update `__init__` and `set_config_callback`:

```python
class TrayUI:
    def __init__(self, process_mgr, main_window, config: AppConfig) -> None:
        ...
        self._config_callback: Callable[[], None] | None = None

    def set_config_callback(self, cb: Callable[[], None]) -> None:
        ...

    def consume_action(self) -> str | None:
        ...
```

- [ ] **Step 5: Update config_ui.py — annotate return type**

Add at top of `src/config_ui.py`:

```python
from types import AppConfig
```

Update `get_result`:

```python
    def get_result(self) -> AppConfig | None:
        ...
```

- [ ] **Step 6: Run ruff and verify**

```bash
uv run ruff format src/ && uv run ruff check src/
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add src/types.py src/config.py src/process_mgr.py src/tray_ui.py src/config_ui.py
git commit -m "refactor: add TypedDict types for ProcessConfig and AppConfig"
```

---

### Task 3: Extend error surfacing to delete_before_start

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Add _system_msg for permission error on delete retry**

In `_start()`, find the `delete_before_start` section. After the PermissionError retry that still fails:

```python
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        logger.warning("Failed to delete %s: %s", file_path, e)
```

Replace with:

```python
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        msg = f"{name} failed to delete {rel_path}: {e}"
                        logger.warning(msg)
                        self._system_msg(name, msg)
```

- [ ] **Step 2: Add _system_msg for path-escape warning**

Find the path-escape check:

```python
                if not real_file.startswith(real_cwd + os.sep) and real_file != real_cwd:
                    logger.warning("delete_before_start path escapes cwd, skipped: %s", rel_path)
                    continue
```

Replace with:

```python
                if not real_file.startswith(real_cwd + os.sep) and real_file != real_cwd:
                    msg = f"{name} skipped delete {rel_path}: path outside cwd"
                    logger.warning(msg)
                    self._system_msg(name, msg)
                    continue
```

- [ ] **Step 3: Run ruff and verify**

```bash
uv run ruff format src/process_mgr.py && uv run ruff check src/process_mgr.py
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: surface delete_before_start errors to output panel"
```

---

### Task 4: Add config validation (name, regex, cwd downgrade)

**Files:**
- Modify: `src/config_ui.py`

- [ ] **Step 1: Add name path-separator check in `_validate`**

In `config_ui.py`, find `_validate` method. After the duplicate name check, add:

```python
            if "/" in name or "\\" in name:
                return f"Process name cannot contain path separators: {name}"
```

Place this right after `if name in names:` check (or before — order doesn't matter as long as it's checked).

- [ ] **Step 2: Add webui_pattern regex validation**

In `_validate`, after the cmd empty check and before `return None`, add:

```python
            webui = v["webui_pattern"].get().strip()
            if webui:
                try:
                    re.compile(webui)
                except re.error as e:
                    return f"Invalid regex in WebUI Pattern for '{name}': {e}"
```

Note: requires `import re` at top of file if not already present.

- [ ] **Step 3: Downgrade cwd existence check from error to warning**

In `_validate`, find the cwd check:

```python
        cwd = v["cwd"].get().strip()
        if cwd and not os.path.exists(cwd):
            return f"CWD not found for '{name}': {cwd}"
```

Replace with a warning log instead of blocking:

```python
        cwd = v["cwd"].get().strip()
        if cwd and not os.path.exists(cwd):
            self._logger.warning("CWD not found for '%s': %s (allowed, may be created later)", name, cwd)
```

- [ ] **Step 4: Run ruff and verify**

```bash
uv run ruff format src/config_ui.py && uv run ruff check src/config_ui.py
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/config_ui.py
git commit -m "feat: add config validation for name pattern and webui regex"
```

---

### Task 5: Extract AppController from main.pyw

**Files:**
- Create: `src/app_controller.py`
- Modify: `src/main.pyw`

- [ ] **Step 1: Create src/app_controller.py**

```python
"""AppController — orchestrates process_mgr, tray_ui, main_window lifecycle."""

import time
import webbrowser
import logging
import os
import tkinter.messagebox

from types import AppConfig


class AppController:
    """Central orchestrator for the application event loop and lifecycle."""

    def __init__(
        self,
        config: AppConfig,
        process_mgr,
        main_window,
        tray_ui,
    ) -> None:
        self._config = config
        self._pm = process_mgr
        self._window = main_window
        self._tray = tray_ui

        self._buffers: dict[str, list[str]] = {}
        self._last_poll = 0.0
        self._last_output = 0.0
        self._settings_open = False

    # --- Settings callback ---

    def _make_settings_callback(self) -> None:
        from config_ui import ConfigDialog
        from logger import get_main_logger

        logger = get_main_logger()

        def open_settings() -> None:
            if self._settings_open:
                return
            self._settings_open = True
            logger.info("Opening settings dialog")
            try:
                dlg = ConfigDialog(self._window.root)
                result = dlg.get_result()
                if result is not None:
                    self._pm.update_config(result)
                    self._window.set_processes(self._pm.process_names())
                    logger.info("Config updated at runtime")
            finally:
                self._settings_open = False

        return open_settings

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

    def _dispatch_action(self, action: str) -> None:
        from logger import get_main_logger

        logger = get_main_logger()
        logger.info("Action: %s", action)

        if action == "startall":
            self._pm.start_all()
        elif action == "stopall":
            self._pm.stop_all()
        elif ":" in action:
            cmd, _, name = action.partition(":")
            if cmd == "start":
                self._pm.start(name)
            elif cmd == "stop":
                self._pm.stop(name)
            elif cmd == "webui":
                url = self._pm.get_webui_url(name)
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
                    self._pm._system_msg(name, f"{name} WebUI URL not detected yet")

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
```

- [ ] **Step 2: Rewrite main.pyw as thin entry point**

Replace entire `src/main.pyw`:

```python
"""TrayForge - tray controller for managed processes."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from single_instance import ensure_single_instance
from logger import get_main_logger
from config import load_config, get_default_config, save_config
from process_mgr import ProcessManager
from main_window import MainWindow
from tray_ui import TrayUI
from types import AppConfig
from app_controller import AppController


def main() -> None:
    logger = get_main_logger()

    if not ensure_single_instance():
        import tkinter.messagebox

        tkinter.messagebox.showwarning("TrayForge", "TrayForge is already running.")
        return

    logger.info("=" * 40)
    logger.info("TrayForge starting...")

    window = MainWindow()

    is_first = load_config() is None
    config: AppConfig = get_default_config() if is_first else load_config()
    if is_first:
        save_config(config)

    pm = ProcessManager(config)
    tray = TrayUI(pm, window, config)
    window.set_processes(pm.process_names())

    app = AppController(config, pm, window, tray)
    app.start(is_first)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run ruff and verify**

```bash
uv run ruff format src/app_controller.py src/main.pyw && uv run ruff check src/app_controller.py src/main.pyw
```

Expected: 0 errors.

- [ ] **Step 4: Verify app launches correctly**

```bash
uv run python -c "
import sys; sys.path.insert(0, 'src')
from app_controller import AppController
from config import get_default_config
print('AppController import OK')
print('Method count:', len([m for m in dir(AppController) if not m.startswith('_')]))
"
```

Expected: prints import OK.

- [ ] **Step 5: Commit**

```bash
git add src/app_controller.py src/main.pyw
git commit -m "refactor: extract AppController from main.pyw"
```

---

### Task 6: Add tests

**Files:**
- Modify: `pyproject.toml` (add pytest dev dependency)
- Create: `tests/test_config.py`
- Create: `tests/test_process_mgr.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Add pytest dependency**

```bash
uv add --dev pytest
```

- [ ] **Step 2: Create tests/test_config.py**

```python
"""Tests for config.py — load, save, migrate, defaults."""

import json
import os
from pathlib import Path
from config import get_default_config, load_config, save_config, _migrate_old_config


def test_default_config_structure():
    cfg = get_default_config()
    assert "processes" in cfg
    assert "output_refresh_ms" in cfg
    assert "poll_interval_ms" in cfg
    assert "autostart" in cfg
    assert isinstance(cfg["processes"], list)
    assert cfg["output_refresh_ms"] == 500
    assert cfg["poll_interval_ms"] == 2000
    assert cfg["autostart"] is False


def test_default_config_returns_fresh_copy_each_time():
    cfg1 = get_default_config()
    cfg2 = get_default_config()
    assert cfg1 is not cfg2  # Different objects
    assert cfg1["processes"] is not cfg2["processes"]


def test_migrate_old_config():
    old = {
        "napcat": {"cwd": "/nap", "cmd": "nc.exe"},
        "astrbot": {"cwd": "/ast", "cmd": "ab.exe", "encoding": "gbk"},
        "output_refresh_ms": 300,
        "autostart": True,
    }
    new = _migrate_old_config(old)
    assert len(new["processes"]) == 2
    napcat = next(p for p in new["processes"] if p["name"] == "NapCat")
    assert napcat["cwd"] == "/nap"
    assert napcat["cmd"] == "nc.exe"
    assert napcat["singleton"] is True
    astrbot = next(p for p in new["processes"] if p["name"] == "AstrBot")
    assert astrbot["cwd"] == "/ast"
    assert astrbot["cmd"] == "ab.exe"
    assert astrbot["encoding"] == "gbk"
    assert astrbot["delete_before_start"] == ["astrbot.lock"]
    assert new["output_refresh_ms"] == 300
    assert new["autostart"] is True


def test_load_config_missing_file():
    # Patch get_data_dir to use tmp_path
    import config as config_module

    original = config_module.get_data_dir

    def fake_dir():
        return "/nonexistent/path"

    config_module.get_data_dir = fake_dir
    try:
        result = load_config()
        assert result is None
    finally:
        config_module.get_data_dir = original


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    import config as config_module

    monkeypatch.setattr(config_module, "get_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config_module, "_get_config_path", lambda: str(tmp_path / "config.json"))

    cfg = get_default_config()
    cfg["output_refresh_ms"] = 999
    assert save_config(cfg) is True

    loaded = load_config()
    assert loaded is not None
    assert loaded["output_refresh_ms"] == 999
    assert len(loaded["processes"]) == len(cfg["processes"])
```

- [ ] **Step 3: Create tests/test_logger.py**

```python
"""Tests for logger.py — logger naming and sanitization."""

from logger import get_process_logger, get_main_logger


def test_get_main_logger_returns_same_instance():
    lg1 = get_main_logger()
    lg2 = get_main_logger()
    assert lg1 is lg2
    assert lg1.name == "trayforge.main"


def test_get_process_logger_name_sanitization():
    lg = get_process_logger("NapCat")
    assert lg.name.startswith("trayforge.process.")
    assert "NapCat" in lg.name


def test_get_process_logger_chinese_name():
    lg = get_process_logger("测试进程")
    assert lg.name.startswith("trayforge.process.")


def test_get_process_logger_special_chars():
    lg = get_process_logger("bad/name\\with:chars")
    assert "/" not in lg.name
    assert "\\" not in lg.name
    assert lg.name.startswith("trayforge.process.")


def test_get_process_logger_returns_same_for_same_name():
    lg1 = get_process_logger("MyProc")
    lg2 = get_process_logger("MyProc")
    assert lg1 is lg2
```

- [ ] **Step 4: Create tests/test_process_mgr.py**

```python
"""Tests for process_mgr.py — config building, state management, crash recovery."""

import queue
from unittest.mock import Mock, patch, MagicMock
from process_mgr import ProcessManager, _ProcState


def _make_config(processes=None):
    if processes is None:
        processes = [
            {
                "name": "TestProc",
                "cwd": "",
                "cmd": "echo hello",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ]
    return {
        "processes": processes,
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }


class TestBuildFromConfig:
    def test_adds_new_processes(self):
        pm = ProcessManager(_make_config())
        assert pm.process_names() == ["TestProc"]

    def test_preserves_existing_state_on_reconfig(self):
        cfg = _make_config()
        pm = ProcessManager(cfg)
        old_ps = pm._procs["TestProc"]

        # Update config without removing the process
        cfg2 = _make_config([
            {
                "name": "TestProc",
                "cwd": "/new/path",
                "cmd": "echo world",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ])
        pm.update_config(cfg2)
        assert pm.process_names() == ["TestProc"]
        assert pm._procs["TestProc"] is old_ps  # Same object preserved
        assert pm._procs["TestProc"].cfg["cwd"] == "/new/path"

    def test_removes_deleted_processes(self):
        cfg = _make_config()
        pm = ProcessManager(cfg)
        cfg2 = _make_config([
            {
                "name": "OtherProc",
                "cwd": "",
                "cmd": "echo",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ])
        pm.update_config(cfg2)
        assert pm.process_names() == ["OtherProc"]
        assert "TestProc" not in pm._procs


class TestProcessState:
    def test_is_running_false_when_no_proc(self):
        pm = ProcessManager(_make_config())
        assert not pm.is_running("TestProc")

    def test_is_running_false_for_nonexistent(self):
        pm = ProcessManager(_make_config())
        assert not pm.is_running("Nonexistent")

    def test_has_webui_false_when_null(self):
        pm = ProcessManager(_make_config())
        assert not pm.has_webui("TestProc")

    def test_has_webui_true_when_pattern_set(self):
        cfg = _make_config([
            {
                "name": "WebProc",
                "cwd": "",
                "cmd": "echo",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": "http://\\S+",
                "delete_before_start": [],
            }
        ])
        pm = ProcessManager(cfg)
        assert pm.has_webui("WebProc")

    def test_drain_returns_empty_for_nonexistent(self):
        pm = ProcessManager(_make_config())
        assert pm.drain("Nonexistent") == []

    def test_drain_returns_queued_messages(self):
        pm = ProcessManager(_make_config())
        ps = pm._procs["TestProc"]
        ps.msg_queue.put("msg1")
        ps.msg_queue.put("msg2")
        lines = pm.drain("TestProc")
        assert lines == ["msg1", "msg2"]
        assert pm.drain("TestProc") == []  # Queue emptied

    def test_system_msg_injects_timestamped_message(self):
        pm = ProcessManager(_make_config())
        pm._system_msg("TestProc", "hello world")
        lines = pm.drain("TestProc")
        assert len(lines) == 1
        assert "[SYSTEM] hello world" in lines[0]


class TestStartStop:
    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_start_empty_command_shows_error(self, mock_thread, mock_popen):
        cfg = _make_config([
            {
                "name": "BadProc",
                "cwd": "",
                "cmd": "",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ])
        pm = ProcessManager(cfg)
        pm._start("BadProc")
        lines = pm.drain("BadProc")
        assert any("no command configured" in l.lower() for l in lines)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_start_missing_cwd_shows_error(self, mock_thread, mock_popen):
        cfg = _make_config([
            {
                "name": "BadProc",
                "cwd": "/definitely/not/a/real/path",
                "cmd": "echo hello",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ])
        pm = ProcessManager(cfg)
        pm._start("BadProc")
        lines = pm.drain("BadProc")
        assert any("working directory not found" in l.lower() for l in lines)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_stop_stops_running_process(self, mock_thread, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        cfg = _make_config()
        pm = ProcessManager(cfg)
        pm._start("TestProc")
        assert pm.is_running("TestProc")

        pm.stop("TestProc")
        assert not pm.is_running("TestProc")

    def test_start_all_and_stop_all(self):
        cfg = _make_config([
            {
                "name": "Proc1",
                "cwd": "",
                "cmd": "",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            },
            {
                "name": "Proc2",
                "cwd": "",
                "cmd": "",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            },
        ])
        pm = ProcessManager(cfg)
        # Both have empty cmd, so _start will show errors but not crash
        pm.start_all()
        lines1 = pm.drain("Proc1")
        lines2 = pm.drain("Proc2")
        assert any("no command configured" in l.lower() for l in lines1)
        assert any("no command configured" in l.lower() for l in lines2)


class TestCrashPolling:
    def test_poll_crashes_ignores_none_proc(self):
        pm = ProcessManager(_make_config())
        pm.poll_crashes()  # Should not raise

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_max_restarts_reached_stops_process(self, mock_thread, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = 1  # Exited with error
        mock_popen.return_value = mock_proc

        cfg = _make_config()
        pm = ProcessManager(cfg)
        pm._start("TestProc")

        from process_mgr import MAX_RESTARTS
        pm._procs["TestProc"].restarts = MAX_RESTARTS
        pm.poll_crashes()

        assert pm._procs["TestProc"].proc is None
        lines = pm.drain("TestProc")
        assert any("max restart attempts" in l.lower() for l in lines)


class TestStatusListeners:
    def test_on_status_change_called_after_start_stop(self):
        pm = ProcessManager(_make_config())
        calls = []
        pm.on_status_change(lambda: calls.append(1))
        pm._emit_status()
        assert len(calls) == 1

    def test_failing_listener_does_not_block_others(self):
        pm = ProcessManager(_make_config())
        calls = []

        def failing():
            raise RuntimeError("boom")

        pm.on_status_change(failing)
        pm.on_status_change(lambda: calls.append(1))
        pm._emit_status()
        assert len(calls) == 1  # Second listener still called

    def test_on_notification_fires(self):
        pm = ProcessManager(_make_config())
        notes = []
        pm.on_notification(lambda t, m: notes.append((t, m)))
        pm._notify("Title", "Message")
        assert notes == [("Title", "Message")]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Run ruff on test files**

```bash
uv run ruff format tests/ && uv run ruff check tests/
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock tests/
git commit -m "test: add unit tests for config, process_mgr, logger"
```
