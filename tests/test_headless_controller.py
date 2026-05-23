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
