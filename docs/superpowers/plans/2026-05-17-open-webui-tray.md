# Open WebUI Tray Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Open WebUI" items to tray right-click menu for NapCat and AstrBot, auto-detecting URLs from process stdout, plus full timestamps on [SYSTEM] messages.

**Architecture:** Parse WebUI URLs in the existing reader thread (process_mgr._reader) before queuing output lines. Store URLs as instance attributes, expose via getters. Tray menu rebuilt on status change includes conditional "Open WebUI" items. Actions dispatched through the existing _enqueue / _tick pattern.

**Tech Stack:** Python stdlib (webbrowser, re, datetime), existing pystray/tkinter

---

## File Structure

| File | Role |
|------|------|
| `src/process_mgr.py` | URL parsing in `_reader`, timestamped `_system_msg`, URL storage/getters, URL clear on stop |
| `src/tray_ui.py` | Conditional "Open WebUI" menu items in `_status_menu` |
| `src/main.pyw` | Handle `webui:napcat` / `webui:astrbot` actions in `_tick` |
| `src/config.py` | Update default config paths |

No new files. No new tests (no test framework configured in project).

---

### Task 1: Update Default Config Paths

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Update `get_default_config()` paths**

In `src/config.py`, change the default `napcat.cwd` and `astrbot.cwd`:

```python
def get_default_config() -> dict:
    """Return default configuration."""
    import locale
    sys_enc = locale.getpreferredencoding() or "utf-8"
    return {
        "napcat": {
            "cwd": "D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell",
            "cmd": "NapCatWinBootMain.exe 2450085301",
            "encoding": "utf-8",
        },
        "astrbot": {
            "cwd": "D:\\Apps\\ai\\AIRobotUI\\astrbot",
            "cmd": "astrbot run",
            "encoding": "utf-8",
        },
        "output_refresh_ms": 500,
        "autostart": False,
    }
```

The only change: `cwd` values. `napcat` was `D:\\Apps\\ai\\napcatqq\\NapCat.44498.Shell`, now `D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell`. `astrbot` was `D:\\Apps\\ai\\astrbot`, now `D:\\Apps\\ai\\AIRobotUI\\astrbot`.

- [ ] **Step 2: Verify the change**

```bash
uv run python -c "from src.config import get_default_config; c = get_default_config(); print(c['napcat']['cwd']); print(c['astrbot']['cwd'])"
```

Expected output:
```
D:\Apps\ai\AIRobotUI\napcatqq\NapCat.44498.Shell
D:\Apps\ai\AIRobotUI\astrbot
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "fix: update default config paths to match actual layout"
```

---

### Task 2: Add Full Timestamps to [SYSTEM] Messages

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Add `import datetime` and `import re` at the top**

In `src/process_mgr.py`, add to existing imports (alongside `import os`, `import logging`):

```python
import re
from datetime import datetime
```

- [ ] **Step 2: Modify `_system_msg` to prefix with timestamp**

Find the existing `_system_msg` method:

```python
    def _system_msg(self, name: str, msg: str) -> None:
        q = self._napcat_queue if name == "napcat" else self._astrbot_queue
        q.put(f"[SYSTEM] {msg}")
```

Replace with:

```python
    def _system_msg(self, name: str, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"
        q = self._napcat_queue if name == "napcat" else self._astrbot_queue
        q.put(f"[{ts}] [SYSTEM] {msg}")
```

- [ ] **Step 3: Verify no import errors**

```bash
uv run python -c "from src.process_mgr import ProcessManager; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: add full timestamps to [SYSTEM] messages"
```

---

### Task 3: Parse WebUI URLs from Process Output

**Files:**
- Modify: `src/process_mgr.py`

- [ ] **Step 1: Add URL storage attributes in `__init__`**

In `ProcessManager.__init__`, add after the existing queue attributes:

```python
        self._napcat_webui_url: str | None = None
        self._astrbot_webui_url: str | None = None
```

- [ ] **Step 2: Add URL parsing in `_reader`**

Find `_reader`:

```python
    def _reader(self, pipe, q: queue.Queue, name: str) -> None:
        proc_logger = (
            get_napcat_logger() if name == "napcat" else get_astrbot_logger()
        )
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                if line:
                    proc_logger.info(line)
                    q.put(line)
        except (ValueError, IOError):
            pass
```

Replace with:

```python
    def _reader(self, pipe, q: queue.Queue, name: str) -> None:
        proc_logger = (
            get_napcat_logger() if name == "napcat" else get_astrbot_logger()
        )
        url_parsed = False
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                if line:
                    proc_logger.info(line)
                    q.put(line)
                    if not url_parsed:
                        url = self._try_parse_webui_url(name, line)
                        if url is not None:
                            setattr(self, f"_{name}_webui_url", url)
                            url_parsed = True
        except (ValueError, IOError):
            pass
```

- [ ] **Step 3: Add `_try_parse_webui_url` helper and public getters**

Add after the existing `_system_msg` method:

```python
    def _try_parse_webui_url(self, name: str, line: str) -> str | None:
        if name == "napcat":
            marker = "[WebUi] WebUi User Panel Url: "
            idx = line.find(marker)
            if idx == -1:
                return None
            rest = line[idx + len(marker):].strip()
        else:  # astrbot
            marker = "Starting WebUI at "
            idx = line.find(marker)
            if idx == -1:
                return None
            rest = line[idx + len(marker):].strip()
        m = re.search(r"https?://\S+", rest)
        return m.group(0) if m else None

    def get_napcat_webui_url(self) -> str | None:
        return self._napcat_webui_url

    def get_astrbot_webui_url(self) -> str | None:
        return self._astrbot_webui_url
```

- [ ] **Step 4: Clear URL on stop**

In `_stop`, after `self._set_proc(name, None)`, add URL clear:

Find:
```python
        self._set_proc(name, None)
        self._system_msg(name, f"{pname} stopped")
```

Replace with:
```python
        self._set_proc(name, None)
        setattr(self, f"_{name}_webui_url", None)
        self._system_msg(name, f"{pname} stopped")
```

- [ ] **Step 5: Verify import/runtime**

```bash
uv run python -c "from src.process_mgr import ProcessManager; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add src/process_mgr.py
git commit -m "feat: parse WebUI URLs from process stdout"
```

---

### Task 4: Add "Open WebUI" Menu Items in Tray

**Files:**
- Modify: `src/tray_ui.py`

- [ ] **Step 1: Add `import webbrowser` and `import re` at top of tray_ui.py**

```python
import webbrowser
import re
```

- [ ] **Step 2: Modify `_status_menu` to include conditional "Open WebUI" item**

Find `_status_menu`:

```python
    def _status_menu(self, name: str) -> Menu:
        def toggle(icon, item):
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            action = "stop" if running else "start"
            self._enqueue(f"{action}:{name}")

        def text(_) -> str:
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            indicator = "\u25CF" if running else "\u25CB"
            status = "Running" if running else "Stopped"
            return f"  {indicator} {status}"

        return Menu(MenuItem(text, toggle))
```

Replace with:

```python
    def _status_menu(self, name: str) -> Menu:
        def toggle(icon, item):
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            action = "stop" if running else "start"
            self._enqueue(f"{action}:{name}")

        def text(_) -> str:
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            indicator = "\u25CF" if running else "\u25CB"
            status = "Running" if running else "Stopped"
            return f"  {indicator} {status}"

        def webui_label(_) -> str:
            url = (
                self._pm.get_napcat_webui_url()
                if name == "napcat"
                else self._pm.get_astrbot_webui_url()
            )
            if url:
                m = re.search(r"https?://([^/\s]+)", url)
                host = m.group(1) if m else ""
                return f"  Open WebUI ({host})" if host else "  Open WebUI"
            return "  Open WebUI"

        def webui_visible(_) -> bool:
            running = (
                self._pm.is_napcat_running()
                if name == "napcat"
                else self._pm.is_astrbot_running()
            )
            if not running:
                return False
            url = (
                self._pm.get_napcat_webui_url()
                if name == "napcat"
                else self._pm.get_astrbot_webui_url()
            )
            return url is not None

        def open_webui(icon, item):
            self._enqueue(f"webui:{name}")

        return Menu(
            MenuItem(text, toggle),
            MenuItem(webui_label, open_webui, visible=webui_visible),
        )
```

- [ ] **Step 5: Verify import**

```bash
uv run python -c "from src.tray_ui import TrayUI; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add src/tray_ui.py
git commit -m "feat: add Open WebUI menu items in tray submenu"
```

---

### Task 5: Handle WebUI Actions in Main Loop

**Files:**
- Modify: `src/main.pyw`

- [ ] **Step 1: Add `import webbrowser` at top of main.pyw**

Add alongside existing stdlib imports:

```python
import webbrowser
```

- [ ] **Step 2: Add webui action handling in `_tick`**

In the action dispatch section of `_tick`, add after the existing `stop:astrbot` case:

Find:
```python
            elif action == "stop:astrbot":
                pm.stop_astrbot()
```

Add after:
```python
            elif action == "webui:napcat":
                url = pm.get_napcat_webui_url()
                if url:
                    ok = webbrowser.open(url)
                    if not ok:
                        logger.warning("Failed to open NapCat WebUI: %s", url)
                else:
                    pm._system_msg("napcat", "NapCat WebUI URL not detected yet")
            elif action == "webui:astrbot":
                url = pm.get_astrbot_webui_url()
                if url:
                    ok = webbrowser.open(url)
                    if not ok:
                        logger.warning("Failed to open AstrBot WebUI: %s", url)
                else:
                    pm._system_msg("astrbot", "AstrBot WebUI URL not detected yet")
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "import webbrowser; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/main.pyw
git commit -m "feat: handle Open WebUI tray actions with webbrowser"
```

---

### Task 6: Manual Integration Verification

**Files:** None (manual test only)

- [ ] **Step 1: Run the application**

```bash
uv run python src/main.pyw
```

- [ ] **Step 2: Verify NapCat WebUI flow**

1. Wait for NapCat to start (logged in, icon turns yellow/green)
2. Right-click tray → NapCat → verify "Open WebUI (127.0.0.1:6100)" appears
3. Click it → browser opens NapCat WebUI
4. Stop NapCat → verify menu item disappears on next right-click

- [ ] **Step 3: Verify AstrBot WebUI flow**

1. Right-click tray → AstrBot → Start
2. Wait for AstrBot to fully start
3. Right-click → AstrBot → verify "Open WebUI (localhost:6185)" appears
4. Click it → browser opens AstrBot WebUI

- [ ] **Step 4: Verify "not detected" message**

1. Restart NapCat, immediately right-click before URL appears in stdout
2. If URL item not visible → correct behavior
3. (Race condition test: in code, temporarily skip URL assignment)
4. Open main window → verify "[SYSTEM] NapCat WebUI URL not detected yet" with timestamp

- [ ] **Step 5: Verify timestamp format**

Open main window, trigger any start/stop action. Verify [SYSTEM] messages show format:
```
[2026-05-17 15:01:08.234] [SYSTEM] NapCat started (PID=xxxxx)
```
Year-month-day hours:minutes:seconds.milliseconds all present.

- [ ] **Step 6: Final commit (if any fixes made)**

```bash
git status
git add <changed files>
git commit -m "chore: integration verification complete"
```
