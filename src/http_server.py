"""HTTP server for CLI control — runs in daemon thread, marshals to main thread."""

import http.server
import threading
import queue
import urllib.parse
from typing import Callable


class _HTTPError(Exception):
    """HTTP error with status code and message."""

    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code
        self.msg = msg


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
            except _HTTPError as e:
                result_queue.put(e)
            except Exception as e:
                result_queue.put(e)
            finally:
                event.set()

        self.root.after(0, wrapper)
        if not event.wait(timeout=5.0):
            raise RuntimeError("HTTP handler timed out waiting for main thread")
        result = result_queue.get()
        if isinstance(result, _HTTPError):
            return result
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

        def do_status() -> str:
            status = self.pm.get_status(name)
            if status is None:
                raise _HTTPError(404, f"Unknown process: {name}")
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
        if isinstance(result, _HTTPError):
            self._send_error(result.code, result.msg)
        else:
            self._send_text(200, result)

    def _handle_webui(self, params: dict) -> None:
        name = params.get("name", [None])[0]
        if not name:
            self._send_error(400, "Missing name parameter")
            return

        def do_webui() -> str:
            if self.pm.get_status(name) is None:
                raise _HTTPError(404, f"Unknown process: {name}")
            url = self.pm.get_webui_url(name)
            if url:
                return url
            return f"{name} WebUI URL not available"

        result = self._marshal(do_webui)
        if isinstance(result, _HTTPError):
            self._send_error(result.code, result.msg)
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
                raise _HTTPError(404, f"Unknown process: {name}")

            if action == "start" and self.pm.is_running(name):
                return f"{name} is already running"
            if action == "stop" and not self.pm.is_running(name):
                return f"{name} is not running"

            action_fn(name)
            past = {"start": "started", "stop": "stopped", "restart": "restarted"}
            return f"{name} {past.get(action, action)}"

        result = self._marshal(do_action)
        # Distinguish 404 (unknown process) from 200 (success/idempotent)
        if isinstance(result, _HTTPError):
            self._send_error(result.code, result.msg)
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
            except _HTTPError as e:
                result_queue.put(e)
            except Exception as e:
                result_queue.put(e)
            finally:
                event.set()

        self.action_queue.put(wrapper)
        if not event.wait(timeout=5.0):
            raise RuntimeError("QueueHandler timed out waiting for main thread")
        result = result_queue.get()
        if isinstance(result, _HTTPError):
            return result
        if isinstance(result, Exception):
            raise result
        return result


def create_server(
    pm, root, reload_fn: Callable[[], bool], handler_cls: type = TrayForgeHTTPHandler
) -> http.server.HTTPServer:
    """Create an HTTPServer. handler_cls defaults to TrayForgeHTTPHandler (tkinter mode).

    For headless mode, pass handler_cls=QueueHandler and root=None.
    """
    handler_cls.pm = pm
    handler_cls.root = root
    handler_cls.reload_fn = reload_fn
    return http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
