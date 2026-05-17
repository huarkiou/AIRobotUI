# Design: Open WebUI from Tray Menu

Date: 2026-05-17

## Overview

Add "Open WebUI" menu items to the system tray right-click menu for both NapCat and AstrBot. URLs are auto-detected from process stdout during startup. System messages in the output window get full timestamps.

## Features

### 1. WebUI URL Parsing from stdout

**File: `src/process_mgr.py`**

In the `_reader` thread, scan each output line before queuing:

- **NapCat pattern**: Line contains `[WebUi] WebUi User Panel Url: `. Extract the first `http://...` URL after that marker.
  - Example input: `[info] [NapCat] [WebUi] WebUi User Panel Url: http://127.0.0.1:6100/webui?token=3f58edc9889d`
  - Extracted: `http://127.0.0.1:6100/webui?token=3f58edc9889d`

- **AstrBot pattern**: Line contains `Starting WebUI at `. Extract the URL after that marker.
  - Example input: `[INFO] [...] Starting WebUI at http://localhost:6185`
  - Extracted: `http://localhost:6185`

Store parsed URLs as instance attributes:
- `self._napcat_webui_url: str | None`
- `self._astrbot_webui_url: str | None`

On `_stop()`, clear the corresponding URL to `None` so it must be re-parsed on next start.

Add public getters:
- `get_napcat_webui_url() -> str | None`
- `get_astrbot_webui_url() -> str | None`

### 2. System Message Timestamps

**File: `src/process_mgr.py`**

Modify `_system_msg()` to prefix messages with a full timestamp:

Format: `[YYYY-MM-DD HH:MM:SS.mmm]`

```
[2026-05-17 15:01:08.234] [SYSTEM] NapCat started (PID=36272)
[2026-05-17 15:01:12.789] [SYSTEM] AstrBot started (PID=24036)
[2026-05-17 15:02:30.001] [SYSTEM] NapCat WebUI URL not detected yet
```

### 3. WebUI Not-Detected Hint

When user clicks "Open WebUI" from the tray menu and the URL has not been parsed yet, emit a system message to the output window:

```
[2026-05-17 HH:MM:SS.mmm] [SYSTEM] NapCat WebUI URL not detected yet
```

This is a one-shot event triggered only by user action — no background polling or auto-retry.

### 4. Tray Menu Items

**File: `src/tray_ui.py`**

Add "Open WebUI" inside each process's submenu (`_status_menu`), **only when**:
1. The process is running (`is_xxx_running()` returns True)
2. The URL has been parsed (`get_xxx_webui_url()` returns non-None)

Menu label format:
- NapCat: `Open WebUI (127.0.0.1:6100)` — extract host:port from URL
- AstrBot: `Open WebUI (localhost:6185)`

If URL extraction fails, fall back to `Open WebUI` without host:port.

Click handler: enqueue `"webui:<name>"` action.

New submenu structure:
```
NapCat >
  ● Running
  Open WebUI (127.0.0.1:6100)      ← new, conditional
---
AstrBot >
  ● Running
  Open WebUI (localhost:6185)       ← new, conditional
```

### 5. Action Handling

**File: `src/main.pyw`**

In `_tick()`, add cases for `"webui:napcat"` and `"webui:astrbot"`:

1. If URL is available: call `webbrowser.open(url)`. On failure (`webbrowser.open` returns False), log at `warning` level, no user-facing error.
2. If URL is None: emit the "not detected yet" system message via `pm._system_msg()`.

### 6. Default Config Paths

**File: `src/config.py`**

Update `get_default_config()` paths to match the actual system layout:

```python
"napcat": {
    "cwd": "D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell",
    ...
},
"astrbot": {
    "cwd": "D:\\Apps\\ai\\AIRobotUI\\astrbot",
    ...
},
```

## Files Changed

| File | Change |
|------|--------|
| `src/process_mgr.py` | URL parsing in `_reader`, `_system_msg` timestamp, URL storage/getters, URL clear on stop |
| `src/tray_ui.py` | "Open WebUI" menu items in `_status_menu`, new action `webui:<name>` |
| `src/main.pyw` | Handle `webui:napcat` / `webui:astrbot` actions in `_tick` |
| `src/config.py` | Update default config paths |

## Error Handling

- URL never parsed → menu item not shown; if user forces via action race, emit "not detected" system message
- `webbrowser.open()` failure → logged at warning level, silent to user
- Process stop clears URL → menu item disappears naturally on next menu refresh
- No new dependencies (`webbrowser` is stdlib)

## Testing

- Unit: URL regex patterns against known output strings
- Manual: start NapCat, verify menu shows "Open WebUI" after URL appears; stop NapCat, verify menu item gone
- Manual: click "Open WebUI" before URL detected, verify system message in output window
- Manual: verify timestamp format on system messages
