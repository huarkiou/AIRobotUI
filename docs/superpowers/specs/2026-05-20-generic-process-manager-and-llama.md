# Generic Process Manager + Llama.cpp Control

## Status
Approved

## Scope

Refactor ProcessManager from hardcoded NapCat/AstrBot pairs to a generic process registry, then add llama.cpp as a third managed process. Also fix the Windows taskbar icon (currently showing a default Python icon instead of the app ring icon).

---

## 1. Config Schema

```json
{
  "processes": [
    {
      "name": "NapCat",
      "cwd": "D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell",
      "cmd": "NapCatWinBootMain.exe 2450085301",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
      "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?://\\S+)",
      "delete_before_start": []
    },
    {
      "name": "AstrBot",
      "cwd": "D:\\Apps\\ai\\AIRobotUI\\astrbot",
      "cmd": "astrbot run",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
      "webui_pattern": "Starting WebUI at (https?://\\S+)",
      "delete_before_start": ["astrbot.lock"]
    },
    {
      "name": "Llama",
      "cwd": "",
      "cmd": "llama-server -m D:\\Apps\\ai\\local_llm\\models\\Qwen3.5-4B-Q8_0\\Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf --mmproj D:\\Apps\\ai\\local_llm\\models\\Qwen3.5-4B-Q8_0\\mmproj-Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-BF16.gguf --host 127.0.0.1 --port 9013 -ngl 99 --api-key sk-huarkiouselfestablished",
      "encoding": "utf-8",
      "singleton": false,
      "autostart": false,
      "webui_pattern": null,
      "delete_before_start": []
    }
  ],
  "output_refresh_ms": 500,
  "autostart": false
}
```

### Fields per process

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Display name and internal key. Must be unique across processes. |
| `cwd` | string | yes | Working directory. Empty string = current working directory. |
| `cmd` | string | yes | Full command line string. If binary is not an absolute path, resolved against cwd then PATH. |
| `encoding` | string | yes | Popen `encoding` for stdout pipe. |
| `singleton` | boolean | yes | If true, before starting, kill all processes matching this process's cwd (via psutil). |
| `autostart` | boolean | yes | Whether to auto-start this process when AIRobotUI launches. |
| `webui_pattern` | string or null | no | Regex with one capture group to extract WebUI URL from output. `null` = no WebUI menu entry. |
| `delete_before_start` | string[] | yes | Files (relative to cwd) to delete before starting. If deletion fails due to file being locked (PermissionError), find the process holding it by matching cwd via psutil, `taskkill /f /t /pid` it, then retry deletion. |

### Top-level fields

| Field | Type | Description |
|---|---|---|
| `processes` | array | Ordered list of managed processes. |
| `output_refresh_ms` | int | Output batch interval in milliseconds. |
| `autostart` | boolean | Whether AIRobotUI itself auto-starts with Windows (registry entry). |

### Config migration

On first run after upgrade, if config.json has the old format (top-level `napcat`/`astrbot` keys), convert to the new `processes` array format and save. Delete old keys. Migration is one-way; no backup of old file.

---

## 2. ProcessManager (`src/process_mgr.py`)

### Internal state

Replace all `_napcat_*` / `_astrbot_*` paired attributes with a single dict:

```python
@dataclass
class _ProcState:
    proc: subprocess.Popen | None = None
    queue: queue.Queue = field(default_factory=queue.Queue)
    restarts: int = 0
    webui_url: str | None = None
    last_restart: float = 0.0
    cooldown_notified: bool = False
    # From config, cached at start:
    cfg: dict = field(default_factory=dict)
```

```python
class ProcessManager:
    _procs: dict[str, _ProcState]  # keyed by name
```

### Public API

| Method | Description |
|---|---|
| `__init__(config)` | Build `_procs` dict from `config["processes"]`. |
| `update_config(config)` | Rebuild `_procs`, preserving running process states (proc, queue, restarts, etc.). If a name is removed from config, stop and drop that process. If added, create new _ProcState. Renaming a process is treated as remove-old + add-new — the old process is stopped. |
| `start(name)` | Start process by name. No-op if already running. |
| `stop(name)` | Stop process by name. Sets restarts to max to disable auto-restart. |
| `start_all()` | Start all configured processes (ignores `autostart` flag — that only controls launch-time auto-start). |
| `stop_all()` | Stop all processes. |
| `shutdown()` | `stop_all()`. |
| `is_running(name)` | bool, checks poll() on stored Popen. |
| `has_webui(name)` | bool, true if `webui_pattern` is not null. |
| `get_webui_url(name)` | str or None. |
| `poll_crashes()` | Iterate `_procs`, detect exited processes, apply cooldown/restart/max-restart logic. |
| `drain(name)` | list[str], drain output queue for a process. |
| `process_names()` | list[str], returns all registered process names in config order. |
| `on_status_change(cb)` / `on_notification(cb)` | Same as before. |

### Start flow (`_start`)

1. If singleton and cwd is non-empty: iterate psutil processes, kill any where `proc.cwd() == this_process.cwd` via `taskkill /f /t /pid`. If cwd is empty, skip singleton check (no cwd to match against).
2. Delete each file in `delete_before_start`; if PermissionError, find any process matching this process's cwd via psutil and kill it, then retry. If the file is locked by a process with a different cwd, deletion fails and is logged as a warning.
3. Resolve binary: if cmd[0] is not absolute and not relative, try `cwd/cmd[0]`, then PATH.
4. `Popen(args, cwd=cwd, stdout=PIPE, stderr=STDOUT, stdin=DEVNULL, text=True, encoding=..., errors="replace", env={PYTHONIOENCODING=utf-8})`
5. Spawn reader thread.

### Reader thread

Same as current: read pipe line by line, strip ANSI, push to queue, attempt `webui_pattern` match on first URL found.

### Stop flow (`_stop`)

`taskkill /f /t /pid <pid>`, set restarts to max (disable auto-restart), emit status.

---

## 3. Main Window (`src/main_window.py`)

### Dynamic tabs

Instead of hardcoded NapCat and AstrBot frames, dynamically create one tab per process name. Tab count rebuilt on config changes (e.g. after settings dialog). Each tab is identical to current: Text widget with scrollbar, Clear/Copy context menu, `MAX_LINES = 5000`.

### App icon — taskbar fix

Current: `root.iconphoto(True, ...)` sets title bar and Alt+Tab but not taskbar icon.

Fix:
1. On startup, save the generated blue ring icon as `icon.ico` in the data dir (`%LOCALAPPDATA%\AIRobotUI\icon.ico`) using Pillow.
2. Call `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIRobotUI")` before creating the root window.
3. After `Tk()`, call `root.iconbitmap(default="path/to/icon.ico")`.

The `.ico` file is regenerated on each startup to ensure it exists (handles cleanup/upgrade scenarios).

---

## 4. Settings Dialog (`src/config_ui.py`)

### Layout

Instead of two fixed LabelFrame sections for NapCat/AstrBot, use a scrollable canvas frame containing a list of process entries. Each entry:

- Collapsed view: `[name]` + Edit/Delete buttons
- Expanded view: fields for name, cwd, cmd, encoding (combobox), singleton (checkbox), autostart (checkbox), webui_pattern (entry, optional), delete_before_start (comma-separated text)

Bottom bar: "Add Process" button appends a new entry with defaults. "Delete" removes — disabled for running processes.

Top-level settings remain: output_refresh_ms, autostart (main program).

### Validation

- Process names must be unique and non-empty.
- cwd must exist if non-empty.
- cmd must be non-empty.

---

## 5. Tray UI (`src/tray_ui.py`)

### Menu structure

Dynamic submenu per process:

```
  [name]
    ● Running / ○ Stopped          ← toggle
    Open WebUI (host:port)          ← only if has_webui(name) and URL resolved
```

Fixed items below processes:

```
  Start All
  Stop All
  ---
  Show/Hide Window
  Settings
  ---
  Exit
```

### Status icon

| Condition | Color |
|---|---|
| All processes running | Green |
| Some running | Yellow |
| None running | Red |

`_refresh_icon()` iterates `_procs` to determine color, rebuilds entire menu.

---

## 6. Main loop (`src/main.pyw`)

### Action dispatch

`consume_action()` returns `"action:name"` strings. Parse generically:

```python
action, _, name = action.partition(":")
match action:
    case "start": pm.start(name)
    case "stop": pm.stop(name)
    case "webui": webbrowser.open(pm.get_webui_url(name))
    case "startall": pm.start_all()
    case "stopall": pm.stop_all()
```

No more hardcoded if/elif for napcat/astrbot.

### Output drain

Iterate all process names, drain each to window tabs:

```python
for name in pm.process_names():
    for line in pm.drain(name):
        window.append_output(name, line)
```

### Autostart on launch

After `tray.run()`, iterate config processes: if `process["autostart"]` is true, call `pm.start(name)`.

### Startup config gate

If first run (no config), open settings dialog immediately (same as current behavior).

---

## 7. Logger (`src/logger.py`)

Current: `napcat.log` and `astrbot.log` are hardcoded.

New: add a `get_process_logger(name)` function analogous to `get_napcat_logger`/`get_astrbot_logger`. Logger name = `airobotui.process.<sanitized_name>`, file = `<sanitized_name>.log`. Retain `get_main_logger()` unchanged. Backward compat: keep `get_napcat_logger`/`get_astrbot_logger` as wrappers for existing callers.

---

## 8. Files Changed

| File | Change |
|---|---|
| `src/config.py` | Default config uses `processes` array. Migration from old format. |
| `src/process_mgr.py` | Full refactor to generic dict-based manager. |
| `src/main_window.py` | Dynamic tabs. Taskbar icon fix. |
| `src/config_ui.py` | Dynamic scrollable process list editor. |
| `src/tray_ui.py` | Dynamic submenus. Three-state icon (all/some/none). |
| `src/main.pyw` | Generic action dispatch, output drain, autostart loop. |
| `src/logger.py` | Add `get_process_logger(name)`. |
| `src/icon.py` | Add `save_ico()` function for taskbar fix. |

## 9. Testing

- Old config migration: create a synthetic old-format config.json, launch, verify new format written and processes work.
- Singleton: start NapCat (singleton=true), verify no duplicate. Start Llama (singleton=false), verify multiple parallel instances.
- delete_before_start: create a fake lock file, assert deleted on start; simulate PermissionError, assert matching process killed then file deleted.
- WebUI: verify menu entry appears/hidden based on webui_pattern.
- Crash recovery: kill a process externally, verify auto-restart with cooldown and max restart limit.
- Taskbar icon: verify blue ring icon appears in Windows taskbar instead of default Python icon.
- Settings: add/remove/edit processes, save, verify UI reflects changes.
