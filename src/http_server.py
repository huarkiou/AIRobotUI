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
        if result.startswith("Unknown process:"):
            self._send_error(404, result)
        else:
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
