# CLI Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CLI control via HTTP — same executable runs GUI (no args) or CLI (with args) that talks to the running GUI instance.

**Architecture:** Unified entry point in `main.pyw` branches on `sys.argv`. GUI mode starts a `http.server.HTTPServer` on `127.0.0.1:0` in a daemon thread, writes port to `cli_port.txt`. CLI mode reads that port file, sends HTTP requests, prints plain-text responses. All handler operations marshal onto tkinter main thread via `root.after()` to preserve single-threaded ProcessManager semantics.

**Tech Stack:** Python stdlib only — `http.server`, `argparse`, `urllib.request`, `threading`, `queue`. No new dependencies.

**Files to create:** `src/http_server.py`, `src/cli.py`, `tests/test_http_server.py`, `tests/test_cli.py`

**Files to modify:** `src/process_mgr.py`, `src/app_controller.py`, `src/main.pyw`, `src/trayforge_types.py`

---

### Task 1: Add `ProcessStatus` TypedDict and `ProcessManager.get_status()`

**Files:**
- Modify: `src/trayforge_types.py`
- Modify: `src/process_mgr.py`
- Modify: `tests/test_process_mgr.py`

- [ ] **Step 1: Add `ProcessStatus` TypedDict to `src/trayforge_types.py`**

Append after the existing `AppConfig` class:

```python
class ProcessStatus(TypedDict):
    name: str
    running: bool
    pid: int | None
    webui_url: str | None
    has_webui: bool
    restarts: int
    max_restarts: int
```

- [ ] **Step 2: Write failing tests for `get_status()` in `tests/test_process_mgr.py`**

Add to the end of the file:

```python
def test_get_status_returns_none_for_unknown_process(pm):
    """pm fixture from conftest provides a ProcessManager with default config."""
    assert pm.get_status("nonexistent") is None


def test_get_status_returns_dict_for_known_process(pm):
    status = pm.get_status("NapCat")
    assert status is not None
    assert status["name"] == "NapCat"
    assert status["running"] is False
    assert status["pid"] is None
    assert status["has_webui"] is True
    assert status["webui_url"] is None
    assert status["restarts"] == 0
    assert status["max_restarts"] == 3


def test_get_status_reflects_running_state(pm):
    # Status before start
    status = pm.get_status("NapCat")
    assert status["running"] is False

    # After start — mock Popen to avoid actually spawning
    import subprocess
    from unittest.mock import patch

    mock_proc = __import__("unittest.mock").MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc):
        pm.start("NapCat")

    status = pm.get_status("NapCat")
    assert status["running"] is True
    assert status["pid"] == 12345
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_process_mgr.py::test_get_status_returns_none_for_unknown_process tests/test_process_mgr.py::test_get_status_returns_dict_for_known_process tests/test_process_mgr.py::test_get_status_reflects_running_state -v
```

Expected: 3 FAIL (AttributeError: 'ProcessManager' object has no attribute 'get_status')

- [ ] **Step 4: Implement `get_status()` in `src/process_mgr.py`**

Add to `ProcessManager` class, after `has_webui()`:

```python
    def get_status(self, name: str) -> dict | None:
        """Return a ProcessStatus dict for the named process, or None if unknown."""
        from trayforge_types import ProcessStatus

        ps = self._procs.get(name)
        if ps is None:
            return None
        running = ps.proc is not None and ps.proc.poll() is None
        result: ProcessStatus = {
            "name": name,
            "running": running,
            "pid": ps.proc.pid if running else None,
            "webui_url": ps.webui_url,
            "has_webui": ps.cfg.get("webui_pattern") is not None,
            "restarts": ps.restarts,
            "max_restarts": MAX_RESTARTS,
        }
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_process_mgr.py::test_get_status_returns_none_for_unknown_process tests/test_process_mgr.py::test_get_status_returns_dict_for_known_process tests/test_process_mgr.py::test_get_status_reflects_running_state -v
```

Expected: 3 PASS

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all 29 existing tests + 3 new = 32 PASS

- [ ] **Step 7: Commit**

```bash
git add src/trayforge_types.py src/process_mgr.py tests/test_process_mgr.py
git commit -m "feat: add ProcessManager.get_status() method"
```

---

### Task 2: Extract `AppController._reload_config()` method

**Files:**
- Modify: `src/app_controller.py`

- [ ] **Step 1: Extract reload logic into a dedicated method**

In `AppController`, add this method after `__init__`:

```python
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
```

- [ ] **Step 2: Update `_dispatch_action` to call the new method**

In `_dispatch_action`, replace the `elif action == "reload":` block (lines that currently do the inline reload) with:

```python
        elif action == "reload":
            self._reload_config()
```

The old block to replace:

```python
        elif action == "reload":
            from config import load_config

            config = load_config()
            if config:
                self._config = config
                self._pm.update_config(config)
                self._window.set_processes(self._pm.process_names())
                logger.info("Config reloaded from disk")
            else:
                logger.error("Failed to reload config — config file missing or corrupted")
```

- [ ] **Step 3: Verify the change — run the app and check "Reload Config" tray menu still works**

Manual test: start the app, modify `config.json`, click "Reload Config" in tray menu. Check logs for "Config reloaded from disk".

- [ ] **Step 4: Commit**

```bash
git add src/app_controller.py
git commit -m "refactor: extract _reload_config() method from _dispatch_action"
```

---

### Task 3: Create HTTP server module

**Files:**
- Create: `src/http_server.py`
- Create: `tests/test_http_server.py`

- [ ] **Step 1: Write the HTTP server module `src/http_server.py`**

```python
"""HTTP server for CLI control — runs in daemon thread, marshals to main thread."""

import http.server
import threading
import queue
import urllib.parse
from typing import Callable


class TrayForgeHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that marshals ProcessManager operations onto tkinter main thread.

    Class attributes (set by create_server factory):
        pm: ProcessManager instance
        root: tkinter.Tk root window
        reload_fn: callable that reloads config, returns bool
    """

    pm = None
    root = None
    reload_fn = None

    # --- HTTP dispatch ---

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        try:
            if path == "/list":
                self._handle_list()
            elif path == "/status":
                self._handle_status(params)
            elif path == "/webui":
                self._handle_webui(params)
            else:
                self._send_error(404, "Not Found")
        except Exception as e:
            self._send_error(500, str(e))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        try:
            if path == "/start":
                self._handle_action("start", params)
            elif path == "/stop":
                self._handle_action("stop", params)
            elif path == "/restart":
                self._handle_action("restart", params)
            elif path == "/reload":
                self._handle_reload()
            else:
                self._send_error(404, "Not Found")
        except Exception as e:
            self._send_error(500, str(e))

    def log_message(self, format, *args):
        """Suppress default stderr logging from http.server."""
        pass

    # --- Marshaling helpers ---

    def _marshal(self, fn):
        """Run fn on tkinter main thread and return its result. Blocks until done."""
        result_queue: queue.Queue = queue.Queue()
        event = threading.Event()

        def wrapper():
            try:
                result_queue.put(fn())
            except Exception as e:
                result_queue.put(e)
            finally:
                event.set()

        self.root.after(0, wrapper)
        event.wait()
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _send_text(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, msg: str) -> None:
        self._send_text(code, msg)

    # --- Handlers ---

    def _handle_list(self) -> None:
        def do_list() -> str:
            names = self.pm.process_names()
            lines = []
            for name in names:
                running = self.pm.is_running(name)
                status = "Running" if running else "Stopped"
                pid_str = ""
                if running:
                    s = self.pm.get_status(name)
                    if s and s["pid"]:
                        pid_str = f"  PID={s['pid']}"
                lines.append(f"{name:<20} {status}{pid_str}")
            return "\n".join(lines)

        result = self._marshal(do_list)
        self._send_text(200, result)

    def _handle_status(self, params: dict) -> None:
        name = params.get("name", [None])[0]
        if not name:
            self._send_error(400, "Missing name parameter")
            return

        def do_status() -> str | None:
            status = self.pm.get_status(name)
            if status is None:
                return None
            lines = [
                f"Name:     {status['name']}",
                f"Status:   {'Running' if status['running'] else 'Stopped'}",
            ]
            if status["running"]:
                lines.append(f"PID:      {status['pid']}")
                if status["webui_url"]:
                    lines.append(f"WebUI:    {status['webui_url']}")
            lines.append(f"Restarts: {status['restarts']}/{status['max_restarts']}")
            return "\n".join(lines)

        result = self._marshal(do_status)
        if result is None:
            self._send_error(404, f"Unknown process: {name}")
        else:
            self._send_text(200, result)

    def _handle_webui(self, params: dict) -> None:
        name = params.get("name", [None])[0]
        if not name:
            self._send_error(400, "Missing name parameter")
            return

        def do_webui() -> str:
            if self.pm.get_status(name) is None:
                return f"Unknown process: {name}"
            url = self.pm.get_webui_url(name)
            if url:
                return url
            return f"{name} WebUI URL not available"

        result = self._marshal(do_webui)
        self._send_text(200, result)

    def _handle_action(self, action: str, params: dict) -> None:
        name = params.get("name", [None])[0]
        if not name:
            self._send_error(400, "Missing name parameter")
            return

        action_fn = getattr(self.pm, action)  # start / stop / restart

        def do_action() -> str:
            if self.pm.get_status(name) is None:
                return f"Unknown process: {name}"

            if action == "start" and self.pm.is_running(name):
                return f"{name} is already running"
            if action == "stop" and not self.pm.is_running(name):
                return f"{name} is not running"

            action_fn(name)
            past = {"start": "started", "stop": "stopped", "restart": "restarted"}
            return f"{name} {past.get(action, action)}"

        result = self._marshal(do_action)
        # Distinguish 404 (unknown process) from 200 (success/idempotent)
        if result.startswith("Unknown process:"):
            self._send_error(404, result)
        else:
            self._send_text(200, result)

    def _handle_reload(self) -> None:
        def do_reload() -> str:
            ok = self.reload_fn()
            if ok:
                return "Config reloaded"
            return "Failed to reload config"

        result = self._marshal(do_reload)
        if "Failed" in result:
            self._send_error(500, result)
        else:
            self._send_text(200, result)


def create_server(pm, root, reload_fn: Callable[[], bool]) -> http.server.HTTPServer:
    """Create an HTTPServer bound to 127.0.0.1:0 with the handler configured.

    Returns the server (not yet started). Caller must read server_address[1]
    for the assigned port, save it, and start serve_forever() in a thread.
    """
    TrayForgeHTTPHandler.pm = pm
    TrayForgeHTTPHandler.root = root
    TrayForgeHTTPHandler.reload_fn = reload_fn
    return http.server.HTTPServer(("127.0.0.1", 0), TrayForgeHTTPHandler)
```

- [ ] **Step 2: Write `tests/test_http_server.py`**

```python
"""Tests for HTTP server endpoints — uses real server in thread with mocked PM."""

import threading
import urllib.request
import urllib.error
from unittest.mock import MagicMock
import pytest
from http_server import create_server


class _FakeRoot:
    """Mimics tkinter root.after(0, fn) by calling fn synchronously."""

    def after(self, _delay, fn, *_args):
        fn()


@pytest.fixture
def server():
    """Start a test HTTP server with mocked ProcessManager."""
    pm = MagicMock()
    pm.process_names.return_value = ["NapCat", "AstrBot"]
    pm.is_running.side_effect = lambda name: name == "NapCat"
    pm.get_status.side_effect = lambda name: (
        {
            "name": "NapCat",
            "running": True,
            "pid": 12345,
            "webui_url": "http://127.0.0.1:6099/webui",
            "has_webui": True,
            "restarts": 1,
            "max_restarts": 3,
        }
        if name == "NapCat"
        else {
            "name": "AstrBot",
            "running": False,
            "pid": None,
            "webui_url": None,
            "has_webui": True,
            "restarts": 0,
            "max_restarts": 3,
        }
    )
    pm.get_webui_url.return_value = "http://127.0.0.1:6099/webui"
    pm.start = MagicMock()
    pm.stop = MagicMock()
    pm.restart = MagicMock()

    root = _FakeRoot()
    reload_fn = MagicMock(return_value=True)

    srv = create_server(pm, root, reload_fn)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    yield pm, port, reload_fn

    srv.shutdown()


def _get(port, path) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _post(port, path) -> tuple[int, str]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


class TestList:
    def test_returns_200_with_process_table(self, server):
        pm, port, _ = server
        code, body = _get(port, "/list")
        assert code == 200
        assert "NapCat" in body
        assert "Running" in body
        assert "PID=12345" in body
        assert "AstrBot" in body
        assert "Stopped" in body


class TestStatus:
    def test_returns_details_for_known_process(self, server):
        _, port, _ = server
        code, body = _get(port, "/status?name=NapCat")
        assert code == 200
        assert "Name:     NapCat" in body
        assert "Running" in body
        assert "PID:      12345" in body
        assert "WebUI:    http://127.0.0.1:6099/webui" in body
        assert "Restarts: 1/3" in body

    def test_returns_404_for_unknown_process(self, server):
        _, port, _ = server
        code, body = _get(port, "/status?name=Ghost")
        assert code == 404
        assert "Unknown process: Ghost" in body

    def test_returns_400_when_name_missing(self, server):
        _, port, _ = server
        code, body = _get(port, "/status")
        assert code == 400


class TestWebUI:
    def test_returns_url_for_running_process(self, server):
        _, port, _ = server
        code, body = _get(port, "/webui?name=NapCat")
        assert code == 200
        assert "http://127.0.0.1:6099/webui" in body

    def test_returns_404_for_unknown(self, server):
        _, port, _ = server
        code, body = _get(port, "/webui?name=Ghost")
        assert code == 404


class TestStart:
    def test_starts_process(self, server):
        pm, port, _ = server
        code, body = _post(port, "/start?name=AstrBot")
        assert code == 200
        assert "AstrBot started" in body
        pm.start.assert_called_once_with("AstrBot")

    def test_idempotent_when_already_running(self, server):
        pm, port, _ = server
        code, body = _post(port, "/start?name=NapCat")
        assert code == 200
        assert "already running" in body
        pm.start.assert_not_called()

    def test_returns_404_for_unknown(self, server):
        _, port, _ = server
        code, body = _post(port, "/start?name=Ghost")
        assert code == 404


class TestStop:
    def test_stops_running_process(self, server):
        pm, port, _ = server
        code, body = _post(port, "/stop?name=NapCat")
        assert code == 200
        assert "NapCat stopped" in body
        pm.stop.assert_called_once_with("NapCat")

    def test_idempotent_when_already_stopped(self, server):
        pm, port, _ = server
        code, body = _post(port, "/stop?name=AstrBot")
        assert code == 200
        assert "not running" in body
        pm.stop.assert_not_called()


class TestRestart:
    def test_restarts_process(self, server):
        pm, port, _ = server
        code, body = _post(port, "/restart?name=NapCat")
        assert code == 200
        assert "NapCat restarted" in body
        pm.restart.assert_called_once_with("NapCat")


class TestReload:
    def test_reloads_config(self, server):
        pm, port, reload_fn = server
        code, body = _post(port, "/reload")
        assert code == 200
        assert "Config reloaded" in body
        reload_fn.assert_called_once()

    def test_reports_failure(self, server):
        pm, port, reload_fn = server
        reload_fn.return_value = False
        code, body = _post(port, "/reload")
        assert code == 500
        assert "Failed to reload config" in body


class TestUnknownEndpoint:
    def test_returns_404(self, server):
        _, port, _ = server
        code, body = _get(port, "/nonexistent")
        assert code == 404
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run pytest tests/test_http_server.py -v
```

Expected: 13 PASS

- [ ] **Step 4: Commit**

```bash
git add src/http_server.py tests/test_http_server.py
git commit -m "feat: add HTTP server module for CLI control"
```

---

### Task 4: Integrate HTTP server into AppController

**Files:**
- Modify: `src/app_controller.py`

- [ ] **Step 1: Add import and server attribute to `__init__`**

Add after the existing imports in `src/app_controller.py`:

```python
import threading
import os
from http_server import create_server
```

Add in `__init__`, after `self._settings_open = False`:

```python
        self._http_server = None
```

- [ ] **Step 2: Start server in `AppController.start()`**

In `AppController.start()`, before the `# Start event loop` comment, add:

```python
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
```

- [ ] **Step 3: Shutdown server and clean up port file in `_cleanup()`**

In `_cleanup()`, after the comment `"""Called when exit is requested during event loop."""` and before flushing output, add:

```python
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
```

- [ ] **Step 4: Verify the app still starts normally**

```bash
uv run python src/main.pyw
```

Expected: app starts, tray icon appears. Check `%LOCALAPPDATA%\TrayForge\cli_port.txt` exists with a valid port number. Check with curl:

```bash
curl http://127.0.0.1:<port>/list
```

Expected: table of configured processes with "Stopped" status.

Exit the app normally (tray menu → Exit). Verify `cli_port.txt` is deleted.

- [ ] **Step 5: Commit**

```bash
git add src/app_controller.py
git commit -m "feat: integrate HTTP server into AppController lifecycle"
```

---

### Task 5: Create CLI module

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI module `src/cli.py`**

```python
"""TrayForge CLI — communicates with running GUI instance via HTTP."""

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from config import get_data_dir


def get_port() -> int | None:
    """Read the port number from cli_port.txt. Returns None if not found."""
    port_file = os.path.join(get_data_dir(), "cli_port.txt")
    try:
        with open(port_file) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def send_request(port: int, path: str, *, method: str = "GET", name: str | None = None) -> tuple[int, str]:
    """Send an HTTP request to the server. Returns (status_code, body_text)."""
    url = f"http://127.0.0.1:{port}{path}"
    if name is not None:
        url += "?" + urllib.parse.urlencode({"name": name})
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trayforge",
        description="TrayForge CLI — control managed processes",
    )
    sub = parser.add_subparsers(dest="command", title="commands")

    sub.add_parser("list", help="List all processes and their status")

    p = sub.add_parser("status", help="Show detailed status for a process")
    p.add_argument("name", help="Process name")

    p = sub.add_parser("start", help="Start a process")
    p.add_argument("name", help="Process name")

    p = sub.add_parser("stop", help="Stop a process")
    p.add_argument("name", help="Process name")

    p = sub.add_parser("restart", help="Restart a process")
    p.add_argument("name", help="Process name")

    p = sub.add_parser("webui", help="Print WebUI URL for a process")
    p.add_argument("name", help="Process name")

    sub.add_parser("reload", help="Tell running instance to reload config from disk")

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()

    # Handle --help / -h explicitly before parse_args for no-arg invocation
    if not argv or (len(argv) == 1 and argv[0] in ("--help", "-h")):
        parser.print_help()
        return 0 if argv else 1

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    port = get_port()
    if port is None:
        print("TrayForge is not running")
        return 1

    cmd = args.command

    try:
        if cmd == "list":
            code, body = send_request(port, "/list")
        elif cmd == "status":
            code, body = send_request(port, "/status", name=args.name)
        elif cmd in ("start", "stop", "restart"):
            code, body = send_request(port, f"/{cmd}", method="POST", name=args.name)
        elif cmd == "webui":
            code, body = send_request(port, "/webui", name=args.name)
        elif cmd == "reload":
            code, body = send_request(port, "/reload", method="POST")
        else:
            parser.print_help()
            return 1

        print(body)
        # Exit 0 on 200, 1 on error codes
        return 0 if code == 200 else 1
    except ConnectionRefusedError:
        print("TrayForge is not running")
        return 1
```

- [ ] **Step 2: Write `tests/test_cli.py`**

```python
"""Tests for CLI argument parsing and HTTP request dispatch."""

from unittest.mock import MagicMock, patch
import pytest
from cli import build_parser, main, get_port


class TestArgParsing:
    def test_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_status_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["status", "NapCat"])
        assert args.command == "status"
        assert args.name == "NapCat"

    def test_start_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["start", "AstrBot"])
        assert args.command == "start"
        assert args.name == "AstrBot"

    def test_stop_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "NapCat"])
        assert args.command == "stop"
        assert args.name == "NapCat"

    def test_restart_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["restart", "NapCat"])
        assert args.command == "restart"
        assert args.name == "NapCat"

    def test_webui_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["webui", "NapCat"])
        assert args.command == "webui"
        assert args.name == "NapCat"

    def test_reload_command(self):
        parser = build_parser()
        args = parser.parse_args(["reload"])
        assert args.command == "reload"

    def test_help_flag(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_name_required_for_status(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["status"])


class TestGetPort:
    def test_returns_port_when_file_exists(self, tmp_path, monkeypatch):
        port_file = tmp_path / "cli_port.txt"
        port_file.write_text("12345")
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() == 12345

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() is None

    def test_returns_none_for_invalid_content(self, tmp_path, monkeypatch):
        port_file = tmp_path / "cli_port.txt"
        port_file.write_text("not-a-number")
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() is None


class TestCLIMain:
    def test_list_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "NapCat    Running\nAstrBot   Stopped")
            result = main(["list"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/list")

    def test_start_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "NapCat started")
            result = main(["start", "NapCat"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/start", method="POST", name="NapCat")

    def test_status_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "Name: NapCat\nStatus: Running")
            result = main(["status", "NapCat"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/status", name="NapCat")

    def test_help_outputs_usage(self, capsys):
        result = main(["--help"])
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert result == 0

    def test_no_args_outputs_usage(self, capsys):
        result = main([])
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert result == 1

    def test_trayforge_not_running(self, capsys):
        with patch("cli.get_port", return_value=None):
            result = main(["list"])
            captured = capsys.readouterr()
            assert "TrayForge is not running" in captured.out
            assert result == 1

    def test_connection_refused(self, capsys):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.side_effect = ConnectionRefusedError
            result = main(["list"])
            captured = capsys.readouterr()
            assert "TrayForge is not running" in captured.out
            assert result == 1

    def test_error_status_code_returns_1(self, capsys):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (404, "Unknown process: Ghost")
            result = main(["status", "Ghost"])
            assert result == 1
```

- [ ] **Step 3: Run CLI tests**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 16 PASS

- [ ] **Step 4: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add CLI module with argparse subcommands"
```

---

### Task 6: Modify main.pyw entry point

**Files:**
- Modify: `src/main.pyw`

- [ ] **Step 1: Add CLI branching to `main.pyw`**

Replace the `if __name__ == "__main__":` block at the end of the file:

```python
if __name__ == "__main__":
    if len(sys.argv) > 1:
        from cli import main as cli_main
        sys.exit(cli_main())
    main()
```

Wait, `cli_main` calls `sys.argv[1:]` by default. But we've already checked `len(sys.argv) > 1`. Actually, `cli_main` with no args uses `sys.argv[1:]`. Let me keep it simple:

```python
if __name__ == "__main__":
    if len(sys.argv) > 1:
        from cli import main as cli_main
        sys.exit(cli_main())
    main()
```

Actually `cli_main()` already handles the case where it receives no args (it prints help and exits 1). But we branch before calling it. So `len(sys.argv) > 1` ensures CLI path. This is correct.

- [ ] **Step 2: Verify both modes work**

GUI mode:
```bash
uv run python src/main.pyw
```
Expected: GUI starts normally.

CLI mode (GUI must be running):
```bash
uv run python src/main.pyw list
uv run python src/main.pyw status NapCat
uv run python src/main.pyw --help
```

Expected: CLI commands return output. `--help` prints usage.

- [ ] **Step 3: Commit**

```bash
git add src/main.pyw
git commit -m "feat: add CLI/GUI mode branching in main.pyw"
```

---

### Task 7: Integration test (manual)

**Files:** none

- [ ] **Step 1: Start TrayForge GUI**

```bash
uv run python src/main.pyw
```

- [ ] **Step 2: Run CLI commands against the running instance**

```bash
# List processes
uv run python src/main.pyw list

# Detailed status
uv run python src/main.pyw status NapCat

# Start a process
uv run python src/main.pyw start NapCat

# Check it's running
uv run python src/main.pyw list

# WebUI URL
uv run python src/main.pyw webui NapCat

# Stop it
uv run python src/main.pyw stop NapCat

# Reload config
uv run python src/main.pyw reload

# Help
uv run python src/main.pyw --help
```

- [ ] **Step 3: Test error cases**

```bash
# Unknown process
uv run python src/main.pyw status Ghost
# Expected: "Unknown process: Ghost"

# Without GUI running (close TrayForge first)
uv run python src/main.pyw list
# Expected: "TrayForge is not running"

# Stop already-stopped process
uv run python src/main.pyw stop NapCat
# Expected: "NapCat is not running"
```

- [ ] **Step 4: Verify port file cleanup**

Start GUI, note port in `%LOCALAPPDATA%\TrayForge\cli_port.txt`. Close GUI via tray Exit. Verify the file is deleted.

---

### Task 8: Ruff format and lint

**Files:** all modified `.py` files

- [ ] **Step 1: Format**

```bash
uv run ruff format src/ tests/
```

- [ ] **Step 2: Lint**

```bash
uv run ruff check src/ tests/
```

Expected: no errors.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (29 existing + 3 new ProcessManager + 13 HTTP server + 16 CLI = 61 total).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: ruff format and lint after CLI feature"
```
