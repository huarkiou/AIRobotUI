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
        if name == "AstrBot"
        else None
    )
    pm.get_webui_url.side_effect = lambda name: (
        "http://127.0.0.1:6099/webui" if name == "NapCat" else None
    )
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
    srv.server_close()


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


class TestWebUIMissingName:
    def test_returns_400_when_name_missing(self, server):
        _, port, _ = server
        code, body = _get(port, "/webui")
        assert code == 400


class TestRestartUnknown:
    def test_returns_404_for_unknown_process(self, server):
        _, port, _ = server
        code, body = _post(port, "/restart?name=Ghost")
        assert code == 404


class TestMethodIsolation:
    def test_post_to_get_endpoint_returns_404(self, server):
        _, port, _ = server
        code, body = _post(port, "/list")
        assert code == 404

    def test_get_to_post_endpoint_returns_404(self, server):
        _, port, _ = server
        code, body = _get(port, "/start?name=NapCat")
        assert code == 404


class TestStartMissingName:
    def test_returns_400_for_missing_name(self, server):
        _, port, _ = server
        code, body = _post(port, "/start")
        assert code == 400


class TestQueueHandler:
    """Tests for QueueHandler mode (headless)."""

    @pytest.fixture
    def qserver(self):
        """Start HTTP server with QueueHandler, drain queue in background."""
        pm = MagicMock()
        pm.process_names.return_value = ["NapCat"]
        pm.is_running.return_value = False
        pm.get_status.side_effect = lambda name: (
            {
                "name": "NapCat",
                "running": False,
                "pid": None,
                "webui_url": None,
                "has_webui": False,
                "restarts": 0,
                "max_restarts": 3,
            }
            if name == "NapCat"
            else None
        )
        pm.start = MagicMock()

        action_queue = __import__("queue").Queue()
        reload_fn = MagicMock(return_value=True)

        from http_server import QueueHandler

        srv = create_server(pm, None, reload_fn, handler_cls=QueueHandler)
        QueueHandler.action_queue = action_queue
        port = srv.server_address[1]

        # Server thread
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()

        # Queue drainer thread (simulates HeadlessController loop)
        exit_flag = threading.Event()

        def drain_loop():
            import time

            while not exit_flag.is_set():
                try:
                    while True:
                        fn = action_queue.get_nowait()
                        fn()
                except __import__("queue").Empty:
                    pass
                time.sleep(0.05)

        dt = threading.Thread(target=drain_loop, daemon=True)
        dt.start()

        yield pm, port

        exit_flag.set()
        srv.shutdown()

    def test_404_for_unknown_process(self, qserver):
        """QueueHandler should propagate _HTTPError as status code, not 500."""
        _, port = qserver
        code, body = _get(port, "/status?name=Ghost")
        assert code == 404
        assert "Unknown process" in body

    def test_200_list_endpoint(self, qserver):
        _, port = qserver
        code, body = _get(port, "/list")
        assert code == 200
        assert "NapCat" in body

    def test_start_dispatches_to_pm(self, qserver):
        pm, port = qserver
        pm.is_running.return_value = False
        code, body = _post(port, "/start?name=NapCat")
        assert code == 200
        pm.start.assert_called_once_with("NapCat")
