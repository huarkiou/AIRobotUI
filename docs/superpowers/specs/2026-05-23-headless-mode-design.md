# Headless Mode — Design Spec

## Overview

Add `--headless` flag to TrayForge so it runs as a background service: ProcessManager + HTTP server
only, no tkinter window, no tray icon. CLI commands work as before via HTTP.

## Entry Point

```
TrayForge.exe              → GUI (unchanged)
TrayForge.exe <cmd>        → CLI client (unchanged)
TrayForge.exe --headless   → headless server (new)
```

## Architecture

```
HeadlessController
├── ProcessManager (shared, no changes)
├── HTTPServer with QueueHandler (new marshal mode)
├── main loop: Queue-driven, sleep(100ms)
└── output → per-process log files (existing logger)
```

No changes to: `app_controller.py`, `main_window.py`, `tray_ui.py`, `process_mgr.py`.

## Components

### `src/headless_controller.py` (~60 lines)

- `HeadlessController(config, pm)`: creates HTTP server with `QueueHandler`, runs main loop
- Main loop: drain HTTP action queue → execute on PM → pm.poll_crashes() → drain output to log → sleep(0.1s)
- Exit: on `POST /shutdown` or KeyboardInterrupt (Ctrl+C)
- No output buffering — process output goes to existing per-process log files via `get_process_logger(name).info(line)`

### `src/http_server.py` additions

- New handler class `QueueHandler` alongside `TrayForgeHTTPHandler`
- `QueueHandler._marshal(fn)`: puts `(fn, result_queue, event)` onto `self.queue`, waits on event
- `QueueHandler` inherits all endpoint methods from `TrayForgeHTTPHandler`
- `create_server` gets `mode="tkinter"|"queue"` parameter
- Queue mode: creates a `queue.Queue()`, sets it on handler, HeadlessController drains it

### `src/main.pyw` changes

```python
if "--headless" in sys.argv:
    from headless_controller import run_headless
    run_headless()
elif len(sys.argv) > 1:
    from cli import main as cli_main
    sys.exit(cli_main())
else:
    main()
```

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | /list, /status, /webui | unchanged |
| POST | /start, /stop, /restart, /reload | unchanged |
| POST | /shutdown | sets exit flag (new) |

## Error Handling

- Ctrl+C → graceful shutdown (stop all processes, delete port file)
- Server already running → single-instance mutex prevents duplicate (unchanged)
- No display → not an issue (headless by definition)

## Tests

- Unit: `test_headless_controller.py` — mock PM, verify queue dispatch loop
- Unit: `test_http_server_queue.py` — verify QueueHandler marshaling
- Integration: `test_integration.py` — add `--headless` variant (no display needed, can run in CI)
