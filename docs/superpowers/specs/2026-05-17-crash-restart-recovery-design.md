# Design: Crash Restart with External Process Recovery

Date: 2026-05-17

## Problem

When AstrBot is restarted via its WebUI (not AIRobotUI), the old process dies but a new AstrBot process (unmanaged) starts. `poll_crashes()` detects the old process exit and tries to restart, but the lock file (`astrbot.lock`) is held by the new external process. The lock deletion silently fails, the new start may conflict with the already-running process, and the cycle repeats — causing infinite restart attempts and notification spam.

## Solution

### 1. Kill External Processes Before Starting

In `_start()`, before launching a new process, kill any existing external instances of the same process. This ensures AIRobotUI is the sole manager.

- **AstrBot**: `taskkill /f /im astrbot.exe` (kill by process name)
- **NapCat**: `taskkill /f /im QQ.exe` + `taskkill /f /im NapCatWinBootMain.exe`

Windows only (`sys.platform == "win32"`). Runs after lock file cleanup, before spawning the new process. Applies to both manual starts and auto-restarts.

Also make lock file deletion more aggressive: if `os.remove()` fails due to file lock, retry via `cmd /c del /f` which can delete files held by other processes on Windows.

```python
# pseudo-code for _start, before subprocess.Popen:
if sys.platform == "win32":
    if name == "astrbot":
        subprocess.run(["taskkill", "/f", "/im", "astrbot.exe"], ...)
        # aggressive lock deletion
        lock = os.path.join(cwd, "astrbot.lock")
        if os.path.exists(lock):
            try:
                os.remove(lock)
            except OSError:
                subprocess.run(["cmd", "/c", "del", "/f", lock], ...)
    elif name == "napcat":
        subprocess.run(["taskkill", "/f", "/im", "QQ.exe"], ...)
        subprocess.run(["taskkill", "/f", "/im", "NapCatWinBootMain.exe"], ...)
```

### 2. Restart Cooldown (60 seconds)

Add `_napcat_last_restart` / `_astrbot_last_restart` attributes (float, `time.monotonic()`). In `poll_crashes()`:

- First crash: restart immediately, record timestamp
- Subsequent crashes within 60s of last restart: skip, log `[SYSTEM]` message "Waiting for restart cooldown..."
- After cooldown expires: execute next restart attempt
- After `_max_restarts` (3) attempts: stop, emit `[SYSTEM]` "Max restart attempts reached"

### 3. System Messages for All Restart Events

Add `_system_msg()` calls to output window:

| Event | Message |
|-------|---------|
| Crash detected | `[SYSTEM] <Name> exited (code=N), restarting (N/3)...` |
| Restart skipped (cooldown) | `[SYSTEM] <Name> restart cooldown, next attempt in Ns` |
| Restart executed | `[SYSTEM] <Name> auto-restarted (N/3)` |
| Max restarts reached | `[SYSTEM] <Name> max restart attempts (3) reached, stopped` |
| External process killed | `[SYSTEM] Killed existing <Name> process before starting` |

### 4. Fix: Clear WebUI URL on Crash

In `poll_crashes()`, after `self._set_proc(name, None)`, clear the WebUI URL attribute:

```python
setattr(self, f"_{name}_webui_url", None)
```

This prevents stale "Open WebUI" menu items after a crash.

## Files Changed

| File | Change |
|------|--------|
| `src/process_mgr.py` | `_start`: external process kill before spawn; lock deletion retry. `poll_crashes`: cooldown logic, system messages, URL clear. `__init__`: new timestamp attributes. |

## Edge Cases

- **No external process running**: `taskkill` returns error, silently ignored
- **Lock file already cleaned**: `del /f` on missing file silently ignored
- **Rapid successive crashes**: cooldown prevents restart storm; only first crash restarts immediately
- **User manually stops during cooldown**: `_stop()` sets `_max_restarts` on the restart counter, preventing further auto-restarts (existing behavior preserved)
- **NapCat**: no lock file, but `QQ.exe` may be running from WebUI restart — killed by taskkill
