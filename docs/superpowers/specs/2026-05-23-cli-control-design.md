# CLI Control — Design Spec

## Overview

Add a CLI mode to TrayForge so users can control processes (start/stop/restart/status/list)
and trigger config reload from the command line. The same executable serves dual purpose:
no arguments launches the GUI (current behavior); arguments launch CLI mode which communicates
with the running GUI instance via HTTP.

## Architecture

```
┌─────────────────────┐     HTTP (127.0.0.1:<port>)     ┌────────────────┐
│  TrayForge GUI      │◄──────────────────────────────►│  TrayForge CLI  │
│  (single instance)  │                                  │  (short-lived)  │
│                     │                                  │                 │
│  HTTPServer thread  │                                  │  reads cli_port │
│  writes cli_port.txt│                                  │  sends request  │
│  handles requests   │                                  │  prints response│
└─────────────────────┘                                  └────────────────┘
```

- **Unified entry point** (`main.pyw`): `sys.argv` length determines mode
  - No args → GUI mode (unchanged)
  - Args → CLI mode (new)
- **Transport**: `http.server.HTTPServer` from stdlib on `127.0.0.1:0` (random port)
- **Port discovery**: port written to `%LOCALAPPDATA%\TrayForge\cli_port.txt` on server start;
  deleted on clean shutdown. CLI reads this file to connect.
- **Thread safety**: HTTP handlers marshal operations onto tkinter main thread via `root.after()`,
  blocking on a `threading.Event` for the result. No locks needed — ProcessManager already
  expects single-threaded access.
- **No new dependencies**. All components from Python stdlib.

## Commands

| CLI invocation            | HTTP request              | Response             |
|---------------------------|---------------------------|----------------------|
| `trayforge list`          | `GET /list`               | Plain-text table     |
| `trayforge status <name>` | `GET /status?name=<name>` | Multi-line details   |
| `trayforge start <name>`  | `POST /start?name=<name>` | "started" or error   |
| `trayforge stop <name>`   | `POST /stop?name=<name>`  | "stopped" or error   |
| `trayforge restart <name>`| `POST /restart?name=<name>`| "restarted" or error |
| `trayforge webui <name>`  | `GET /webui?name=<name>`  | URL or "not avail."  |
| `trayforge reload`        | `POST /reload`            | "reloaded" or error  |
| `trayforge --help`        | N/A                       | Usage text           |

Config editing (`trayforge config`) is intentionally excluded. Users edit `config.json` directly
and use `trayforge reload` to apply changes.

`startall` / `stopall` excluded. Users script `start`/`stop` per-process as needed.

## CLI Component (`src/cli.py`)

- Returns exit code 0 on success, 1 on error.
- Uses `argparse` with subparsers for the 7 commands.
- Responds to `--help` with formatted usage listing all subcommands.
- Reads port from `cli_port.txt` in data dir. If file missing → "TrayForge is not running", exit 1.
- Sends HTTP request, prints plain-text response body to stdout.
- On `ConnectionRefusedError` → "TrayForge is not running", exit 1.

## HTTP Server Component (`src/http_server.py` or inline in `app_controller.py`)

- Daemon thread started in `AppController.start()` before entering mainloop.
- Binds to `127.0.0.1:0`, writes actual port to `cli_port.txt`.
- All handler methods use `root.after(0, fn)` + `threading.Event` to serialize onto main thread.
- Response content type: `text/plain; charset=utf-8`.
- Status codes: 200 (success), 400 (bad request / missing name), 404 (unknown endpoint / unknown process), 500 (operation failed).

### Endpoint details

**GET /list** — Returns a table:
```
NapCat    Stopped
AstrBot   Running  PID=12345
```
Columns: name, status (Running/Stopped), optional PID for running processes.

**GET /status?name=X** — Returns multi-line details:
```
Name:     NapCat
Status:   Running
PID:      12345
WebUI:    http://127.0.0.1:6099/webui
Restarts: 0/3
```

**POST /start?name=X** — Starts process, returns `NapCat started` or error message. Idempotent: if already running, returns `NapCat is already running`.

**POST /stop?name=X** — Stops process via ProcessManager. Idempotent: if not running, returns `NapCat is not running`.

**POST /restart?name=X** — Restarts. Returns `NapCat restarted`.

**GET /webui?name=X** — Returns webui URL or `NapCat WebUI URL not available`.

**POST /reload** — Calls config reload, returns `Config reloaded` or error.

## Error Handling

| Scenario | CLI behavior |
|---|---|
| GUI not running (no port file / connection refused) | "TrayForge is not running", exit 1 |
| Unknown process name | "Unknown process: <name>", exit 1 |
| Start already-running process | "<name> is already running", exit 0 |
| Stop already-stopped process | "<name> is not running", exit 0 |
| Start fails (bad cmd/cwd) | Error message from server, exit 1 |
| Stale port file (server crashed, new instance on different port) | Connection refused → "not running" |
| Concurrent CLI calls | Serialized via tkinter event queue; no race conditions |

## Threading

- HTTP server runs in daemon thread, accepts requests, posts to main thread via `root.after()`.
- Handler blocks on `threading.Event` until main thread processes and sets result.
- Main thread (`_tick` event loop) handles one request per iteration alongside existing polling.
- No shared mutable state between HTTP thread and main thread besides the Event + result variable.

## Lifecycle

1. GUI starts → `AppController.start()` creates `HTTPServer`, starts daemon thread, writes `cli_port.txt`.
2. GUI running → server accepts CLI requests, processes via main thread.
3. GUI exit → `_cleanup()` calls `server.shutdown()`, deletes `cli_port.txt`.
4. On crash → `cli_port.txt` may linger. Next GUI start overwrites it with new port. Stale file is harmless (CLI gets connection refused).

## Entry Point Changes (`main.pyw`)

```python
if len(sys.argv) == 1:
    # GUI mode — existing code unchanged
    ...
else:
    from cli import main as cli_main
    sys.exit(cli_main(sys.argv[1:]))
```

## PyInstaller

No changes needed. The `.spec` already bundles `src/` as a directory. The unified entry point means
the same `.exe` works for both GUI and CLI.

## Testing

- Unit tests for CLI argument parsing (`test_cli.py`): verify all subcommands parse correctly,
  unknown args produce help, `--help` works.
- Unit tests for HTTP server handlers (`test_http_server.py`): mock ProcessManager, verify
  each endpoint returns correct status and body.
- CLI tests can run without GUI by mocking HTTP responses.
- Integration test: start GUI, run CLI commands against it, verify process state changes.
