"""Integration tests — start TrayForge GUI subprocess, exercise HTTP API, verify cleanup.

Uses TRAYFORGE_DATA_DIR env var to isolate from production config.
Requires a desktop session (tkinter needs a display).
Run with: uv run pytest tests/test_integration.py -v -s
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest


EXE = os.path.join(os.path.dirname(__file__), "..", "dist", "TrayForge.exe")
SRC = os.path.join(os.path.dirname(__file__), "..", "src", "main.pyw")

# Test data directory — isolated from production %LOCALAPPDATA%\TrayForge\
TEST_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "TrayForgeTest",
)


def _get_server_exe():
    """Prefer built exe; fall back to source."""
    if os.path.exists(EXE):
        return [EXE]
    return [sys.executable, SRC]


def _wait_for_port(timeout=15):
    """Poll cli_port.txt until a port appears. Returns port or None on timeout."""
    port_file = os.path.join(TEST_DATA_DIR, "cli_port.txt")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with open(port_file) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            time.sleep(0.3)
    return None


def _http_get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _http_post(port, path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _write_test_config():
    """Write a test config into TEST_DATA_DIR."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    config_path = os.path.join(TEST_DATA_DIR, "config.json")
    test_config = {
        "processes": [
            {
                "name": "TestProc",
                "cwd": "",
                "cmd": f'{sys.executable} -c "import time; time.sleep(300)"',
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "cleanup_cwd": False,
                "webui_pattern": None,
                "delete_before_start": [],
            },
        ],
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(test_config, f, indent=2)


def _has_display() -> bool:
    """Check if a display is available for tkinter."""
    if sys.platform == "win32":
        # Windows: try to create a hidden Tk window
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.destroy()
            return True
        except Exception:
            return False
    else:
        # Linux/macOS: check DISPLAY env var
        return bool(os.environ.get("DISPLAY"))


@pytest.fixture(scope="module")
def server():
    """Start TrayForge GUI in isolated test dir, yield port, then kill and clean up."""
    if not _has_display():
        pytest.skip("No display available (headless environment)")
    # Kill stale processes from previous failed runs
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/f", "/im", "TrayForge.exe"],
            capture_output=True,
            timeout=5,
        )

    # Clean up from previous test runs and set up fresh test directory
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    _write_test_config()

    exe = _get_server_exe()

    # Build env that isolates the subprocess to TEST_DATA_DIR
    env = os.environ.copy()
    env["TRAYFORGE_DATA_DIR"] = TEST_DATA_DIR

    proc = subprocess.Popen(
        exe,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    try:
        # Wait for port file
        port = _wait_for_port(timeout=20)
        if port is None:
            pytest.fail("GUI did not start: port file never appeared")

        # Wait for HTTP server to accept connections
        deadline = time.monotonic() + 10
        ready = False
        while time.monotonic() < deadline:
            try:
                code, _ = _http_get(port, "/list")
                if code == 200:
                    ready = True
                    break
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                time.sleep(0.5)
        if not ready:
            pytest.fail("GUI started but HTTP server not responding")

        yield port

    finally:
        # Always clean up
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        # Remove test data directory
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

        # Aggressive: ensure no TrayForge left behind
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/f", "/im", "TrayForge.exe"],
                capture_output=True,
                timeout=5,
            )


class TestIntegration:
    """End-to-end tests against a running TrayForge GUI."""

    def test_list_returns_processes(self, server):
        code, body = _http_get(server, "/list")
        assert code == 200, f"Expected 200, got {code}: {body}"
        assert "TestProc" in body
        assert "Stopped" in body

    def test_status_unknown_process(self, server):
        code, body = _http_get(server, "/status?name=Ghost")
        assert code == 404
        assert "Unknown process" in body

    def test_status_known_process(self, server):
        code, body = _http_get(server, "/status?name=TestProc")
        assert code == 200
        assert "TestProc" in body
        assert "Stopped" in body

    def test_reload_returns_ok(self, server):
        code, body = _http_post(server, "/reload")
        assert code == 200
        assert "Config reloaded" in body

    def test_webui_not_available_for_process_without_pattern(self, server):
        code, body = _http_get(server, "/webui?name=TestProc")
        assert code == 200
        assert "not available" in body

    def test_unknown_endpoint_returns_404(self, server):
        code, body = _http_get(server, "/nonexistent")
        assert code == 404

    def test_port_file_exists_while_server_running(self, server):
        port_file = os.path.join(TEST_DATA_DIR, "cli_port.txt")
        assert os.path.exists(port_file), (
            f"Port file {port_file} should exist while server is running"
        )
        with open(port_file) as f:
            read_port = int(f.read().strip())
        assert read_port == server
