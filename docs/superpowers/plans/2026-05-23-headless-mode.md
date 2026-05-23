# Headless Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--headless` flag to run ProcessManager + HTTP server without tkinter GUI.

**Architecture:** New `HeadlessController` with Queue-based main loop. HTTP server gets a QueueHandler variant. No changes to existing GUI code.

**Tech Stack:** Python stdlib only — `threading`, `queue`, `http.server`. No new dependencies.

**Files to create:** `src/headless_controller.py`, `tests/test_headless_controller.py`

**Files to modify:** `src/http_server.py`, `src/main.pyw`

---

### Task 1: Add QueueHandler mode to HTTP server

**Files:**
- Modify: `src/http_server.py`

- [ ] **Step 1: Read the current `src/http_server.py` to understand existing structure**

Key things to note:
- `TrayForgeHTTPHandler` has `_marshal(fn)` that uses `self.root.after(0, wrapper)`
- `create_server(pm, root, reload_fn)` factory sets class attributes and returns `HTTPServer`
- All endpoint handlers (`_handle_list`, `_handle_status`, etc.) are on `TrayForgeHTTPHandler`

- [ ] **Step 2: Add `QueueHandler` class**

Add after `TrayForgeHTTPHandler` class, before `create_server`:

```python
class QueueHandler(TrayForgeHTTPHandler):
    """HTTP handler variant that marshals to a queue consumed by HeadlessController.

    Class attribute (set by factory):
        action_queue: queue.Queue — shared queue for marshaling to main thread
    """

    action_queue = None

    def _marshal(self, fn):
        """Override: post to action_queue instead of root.after(), block on per-request Event."""
        result_queue: queue.Queue = queue.Queue()
        event = threading.Event()

        def wrapper():
            try:
                result_queue.put(fn())
            except Exception as e:
                result_queue.put(e)
            finally:
                event.set()

        self.action_queue.put(wrapper)
        event.wait()
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result
```

- [ ] **Step 3: Extend `create_server` with a `handler_cls` parameter**

Replace the existing `create_server`:

```python
def create_server(pm, root, reload_fn: Callable[[], bool],
                  handler_cls: type = TrayForgeHTTPHandler) -> http.server.HTTPServer:
    """Create an HTTPServer. handler_cls defaults to TrayForgeHTTPHandler (tkinter mode).

    For headless mode, pass handler_cls=QueueHandler and root=None.
    """
    handler_cls.pm = pm
    handler_cls.root = root
    handler_cls.reload_fn = reload_fn
    return http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
```

- [ ] **Step 4: Verify existing tests still pass**

```bash
uv run pytest tests/test_http_server.py -v
```

Expected: 20 PASS (no breakage in tkinter mode)

- [ ] **Step 5: Commit**

```bash
git add src/http_server.py
git commit -m "feat: add QueueHandler mode to HTTP server for headless support"
```

---

### Task 2: Create HeadlessController

**Files:**
- Create: `src/headless_controller.py`
- Create: `tests/test_headless_controller.py`

- [ ] **Step 1: Write failing tests for `HeadlessController` in `tests/test_headless_controller.py`**

```python
"""Tests for HeadlessController — Queue-based main loop without tkinter."""

import threading
import time
import urllib.request
import urllib.error
from unittest.mock import MagicMock
import pytest
from http_server import create_server, QueueHandler


@pytest.fixture
def headless_server():
    """Start HTTP server in headless mode (QueueHandler), run a controller loop."""
    pm = MagicMock()
    pm.process_names.return_value = ["TestProc"]
    pm.is_running.return_value = False
    pm.get_status.return_value = {
        "name": "TestProc",
        "running": False,
        "pid": None,
        "webui_url": None,
        "has_webui": False,
        "restarts": 0,
        "max_restarts": 3,
    }
    pm.start = MagicMock()
    pm.poll_crashes = MagicMock()
    pm.drain.return_value = []

    reload_fn = MagicMock(return_value=True)

    action_queue = __import__("queue").Queue()
    srv = create_server(pm, None, reload_fn, handler_cls=QueueHandler)
    QueueHandler.action_queue = action_queue
    port = srv.server_address[1]

    # Daemon thread for HTTP server
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    # Run controller loop in background thread
    exit_flag = threading.Event()

    def controller_loop():
        while not exit_flag.is_set():
            # Drain action queue
            try:
                while True:
                    fn = action_queue.get_nowait()
                    fn()
            except __import__("queue").Empty:
                pass
            pm.poll_crashes()
            time.sleep(0.1)

    ctrl_thread = threading.Thread(target=controller_loop, daemon=True)
    ctrl_thread.start()

    yield pm, port

    exit_flag.set()
    srv.shutdown()


def _get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _post(port, path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


class TestHeadless:
    def test_list_endpoint_works(self, headless_server):
        pm, port = headless_server
        code, body = _get(port, "/list")
        assert code == 200
        assert "TestProc" in body

    def test_start_endpoint_dispatches_to_pm(self, headless_server):
        pm, port = headless_server
        pm.is_running.return_value = False
        code, body = _post(port, "/start?name=TestProc")
        assert code == 200
        pm.start.assert_called_once_with("TestProc")

    def test_reload_endpoint_works(self, headless_server):
        pm, port = headless_server
        code, body = _post(port, "/reload")
        assert code == 200
        assert "Config reloaded" in body

    def test_crash_poll_gets_called(self, headless_server):
        pm, port = headless_server
        # Let loop run a few cycles
        time.sleep(0.5)
        assert pm.poll_crashes.call_count > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_headless_controller.py -v
```

Expected: FAIL (module not found / no headless_controller yet)

- [ ] **Step 3: Write `src/headless_controller.py`**

```python
"""Headless mode — run ProcessManager + HTTP server without tkinter GUI."""

import os
import queue
import threading
import time
from config import get_data_dir, load_config
from http_server import create_server, QueueHandler
from logger import get_main_logger, get_process_logger


def run_headless() -> None:
    """Entry point for --headless mode. Blocks until shutdown or KeyboardInterrupt."""
    logger = get_main_logger()
    logger.info("Starting TrayForge in headless mode")

    config = load_config()
    if config is None:
        from config import get_default_config, save_config
        config = get_default_config()
        save_config(config)

    from process_mgr import ProcessManager
    pm = ProcessManager(config)

    action_queue: queue.Queue = queue.Queue()

    # HTTP server with QueueHandler
    reload_fn = _make_reload_fn(config, pm)
    server = create_server(pm, None, reload_fn, handler_cls=QueueHandler)
    QueueHandler.action_queue = action_queue
    port = server.server_address[1]

    threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="http-server",
    ).start()

    # Write port file
    port_file = os.path.join(get_data_dir(), "cli_port.txt")
    with open(port_file, "w") as f:
        f.write(str(port))
    logger.info("HTTP server listening on 127.0.0.1:%d", port)

    # Autostart processes
    for proc in config.get("processes", []):
        if proc.get("autostart"):
            logger.info("Autostart: %s", proc["name"])
            pm.start(proc["name"])

    last_poll = 0.0
    poll_interval = config.get("poll_interval_ms", 2000) / 1000.0
    exit_flag = False

    try:
        while not exit_flag:
            # Drain action queue
            try:
                while True:
                    fn = action_queue.get_nowait()
                    fn()
            except queue.Empty:
                pass

            # Poll crashes
            now = time.monotonic()
            if now - last_poll >= poll_interval:
                last_poll = now
                pm.poll_crashes()

            # Drain output to process log files
            for name in pm.process_names():
                proc_logger = get_process_logger(name)
                for line in pm.drain(name):
                    proc_logger.info(line)

            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down")
    finally:
        logger.info("Stopping HTTP server")
        server.shutdown()
        try:
            os.remove(port_file)
        except OSError:
            pass
        pm.shutdown()
        logger.info("Headless mode exited")


def _make_reload_fn(config, pm):
    """Create a reload callback for the headless controller."""
    from logger import get_main_logger
    from config import load_config

    logger = get_main_logger()

    def reload_config() -> bool:
        new_config = load_config()
        if new_config:
            config.clear()
            config.update(new_config)
            pm.update_config(new_config)
            logger.info("Config reloaded from disk")
            return True
        logger.error("Failed to reload config")
        return False

    return reload_config
```

- [ ] **Step 4: Run headless controller tests to verify they pass**

```bash
uv run pytest tests/test_headless_controller.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/headless_controller.py tests/test_headless_controller.py
git commit -m "feat: add HeadlessController with Queue-based event loop"
```

---

### Task 3: Add --headless branch to main.pyw

**Files:**
- Modify: `src/main.pyw`

- [ ] **Step 1: Read current `main.pyw` to find exact text to modify**

Current block:
```python
if __name__ == "__main__":
    if len(sys.argv) > 1:
        from cli import main as cli_main
        sys.exit(cli_main())
    main()
```

- [ ] **Step 2: Add `--headless` check before CLI check**

Replace with:
```python
if __name__ == "__main__":
    if "--headless" in sys.argv:
        from headless_controller import run_headless
        run_headless()
    elif len(sys.argv) > 1:
        from cli import main as cli_main
        sys.exit(cli_main())
    else:
        main()
```

- [ ] **Step 3: Manual test — start headless mode, verify with CLI**

Terminal 1:
```bash
uv run python src/main.pyw --headless
# Should print: HTTP server listening on 127.0.0.1:<port>
```

Terminal 2:
```bash
uv run python src/main.pyw list
uv run python src/main.pyw status NapCat
```

Terminal 1: Press Ctrl+C, verify clean shutdown.

- [ ] **Step 4: Commit**

```bash
git add src/main.pyw
git commit -m "feat: add --headless entry point to main.pyw"
```

---

### Task 4: Ruff format, lint, full test suite

**Files:** all modified

- [ ] **Step 1: Format and lint**

```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/
```

Expected: no errors.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests pass + 4 new headless tests.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: ruff format and lint after headless mode"
```
