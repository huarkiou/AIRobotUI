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


def send_request(
    port: int, path: str, *, method: str = "GET", name: str | None = None
) -> tuple[int, str]:
    """Send an HTTP request to the server. Returns (status_code, body_text).
    status_code 0 means a transport-level error (connection refused, timeout, etc.).
    """
    url = f"http://127.0.0.1:{port}{path}"
    if name is not None:
        url += "?" + urllib.parse.urlencode({"name": name})
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except urllib.error.URLError:
        return 0, "TrayForge is not running"


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
        return 0 if code == 200 else 1
    except Exception:
        print("TrayForge is not running")
        return 1
