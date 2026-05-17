# Crash Restart Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent infinite restart loops when AstrBot/NapCat are restarted externally (e.g., WebUI). Kill external processes before spawning, add 60s cooldown between restarts, and log all restart events to the output window.

**Architecture:** Single-file change to `src/process_mgr.py`. `_start()` gains external process cleanup. `poll_crashes()` gains cooldown tracking, system messages, and URL cleanup.

**Tech Stack:** Python stdlib, existing Windows taskkill pattern.

---

## File Structure

| File | Role |
|------|------|
| `src/process_mgr.py` | All changes: init, _start, poll_crashes |

No new files.

---

### Task 1: Add Restart Cooldown Attributes

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Add `import time` at top**

```python
import time
```

- [ ] **Step 2: Add cooldown attributes in `__init__`**

After the existing `self._astrbot_webui_url` line, add:

```python
        self._napcat_last_restart: float = 0.0
        self._astrbot_last_restart: float = 0.0
```

- [ ] **Step 3: Verify**

```bash
uv run python -c "from src.process_mgr import ProcessManager; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: add restart cooldown timestamps to ProcessManager"
```

---

### Task 2: Add External Process Cleanup in `_start`

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Add cleanup block in `_start`, after lock file section and before cwd check**

Find the lock file cleanup:
```python
        # Clean stale lock files
        if name == "astrbot":
            lock = os.path.join(cwd, "astrbot.lock")
            if os.path.exists(lock):
                try:
                    os.remove(lock)
                except OSError:
                    pass
```

Replace with:
```python
        # Kill any external instances & clean locks (Windows only)
        if sys.platform == "win32":
            if name == "astrbot":
                subprocess.run(
                    ["taskkill", "/f", "/im", "astrbot.exe"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                lock = os.path.join(cwd, "astrbot.lock")
                if os.path.exists(lock):
                    try:
                        os.remove(lock)
                    except OSError:
                        subprocess.run(
                            ["cmd", "/c", "del", "/f", lock],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
            elif name == "napcat":
                subprocess.run(
                    ["taskkill", "/f", "/im", "QQ.exe"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                subprocess.run(
                    ["taskkill", "/f", "/im", "NapCatWinBootMain.exe"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
```

- [ ] **Step 2: Verify**

```bash
uv run python -c "from src.process_mgr import ProcessManager; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: kill external process instances before starting managed process"
```

---

### Task 3: Rewrite `poll_crashes` with Cooldown and System Messages

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Replace `poll_crashes` method**

Find the entire `poll_crashes` method and replace with:

```python
    def poll_crashes(self) -> None:
        """Check for unexpected exits; auto-restart with cooldown."""
        RESTART_COOLDOWN = 60.0
        for name in ("napcat", "astrbot"):
            proc = self._get_proc(name)
            if proc is None:
                continue
            ret = proc.poll()
            if ret is not None:
                pname = self._name(name)
                logger = get_main_logger()
                count = self._restart_count(name)

                # Mark process as dead and clear stale state
                self._set_proc(name, None)
                setattr(self, f"_{name}_webui_url", None)

                logger.warning(
                    "%s exited code=%d restarts=%d/%d",
                    pname, ret, count, self._max_restarts,
                )

                if count >= self._max_restarts:
                    self._system_msg(
                        name,
                        f"{pname} max restart attempts ({self._max_restarts}) reached, stopped",
                    )
                    self._notify(
                        f"{pname} Stopped",
                        "Max restart attempts reached.",
                    )
                    continue

                # Cooldown check
                now = time.monotonic()
                last = getattr(self, f"_{name}_last_restart")
                if count > 0 and now - last < RESTART_COOLDOWN:
                    remaining = int(RESTART_COOLDOWN - (now - last))
                    self._system_msg(
                        name,
                        f"{pname} restart cooldown, next attempt in {remaining}s",
                    )
                    continue

                # Execute restart
                self._inc_restart(name)
                setattr(self, f"_{name}_last_restart", now)
                self._system_msg(
                    name,
                    f"{pname} exited (code={ret}), auto-restarting ({count + 1}/{self._max_restarts})...",
                )
                self._notify(
                    f"{pname} Crashed",
                    f"Auto-restarting ({count + 1}/{self._max_restarts})...",
                )
                self._start(name)
                self._emit_status()
```

Key logic:
- `count` is 0 on first crash (before increment), so `count > 0` means "not the first restart" — cooldown applies to retries 2 and 3
- `count >= self._max_restarts` — after 3 starts + crashes, stop. Note: `_start` calls `_reset_restart` on success, so this only triggers if the restart itself fails
- `setattr(self, f"_{name}_last_restart", now)` — records time after successful restart dispatch
- `_emit_status()` called after each restart to refresh tray menu

- [ ] **Step 2: Verify**

```bash
uv run python -c "from src.process_mgr import ProcessManager; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: add restart cooldown and system messages to poll_crashes"
```

---

### Task 4: Manual Verification

**Files:** None

- [ ] **Step 1: Run the app and test normal crash restart**

1. Start AstrBot via tray
2. Kill it: `taskkill /f /im astrbot.exe`
3. Verify output window shows: `[SYSTEM] AstrBot exited (code=1), auto-restarting (1/3)...`
4. Verify it restarts after moment
5. Kill it again within 60s
6. Verify output window shows cooldown message: `[SYSTEM] AstrBot restart cooldown, next attempt in Ns`
7. Wait for cooldown, verify it restarts again

- [ ] **Step 2: Test external restart takeover**

1. Start AstrBot via tray
2. Restart it via WebUI
3. Verify tray doesn't spam notifications (should detect crash once, kill external process, take over)
4. Check output window for `[SYSTEM] AstrBot exited...` message

- [ ] **Step 3: Verify max restarts**

1. Kill AstrBot repeatedly (3+ times in quick succession, bypass cooldown for testing)
2. Verify after 3 attempts it stops with `[SYSTEM] AstrBot max restart attempts (3) reached, stopped`

- [ ] **Step 4: Commit if fixes needed**

```bash
git add <changed files>
git commit -m "chore: manual verification complete"
```
