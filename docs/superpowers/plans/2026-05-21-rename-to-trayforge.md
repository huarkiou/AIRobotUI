# Rename AIRobotUI → TrayForge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the AIRobotUI project to TrayForge across all source code, config, scripts, CI, docs, and directory structure. Zero functional changes.

**Architecture:** Sequential find-and-replace across ~15 files in order of dependency: data/log paths first, then entry points, then UI strings, then build/docs. Verify with ruff format/check after source changes, then manual launch check.

**Tech Stack:** Python 3.11+, uv, ruff

---

### Task 1: Rename src/config.py and src/logger.py (data/log paths)

**Files:**
- Modify: `src/config.py`
- Modify: `src/logger.py`

- [ ] **Step 1: Update config.py**

Replace `"AIRobotUI"` with `"TrayForge"` in `get_data_dir()` and the docstring.

In `src/config.py`, replace the docstring line 1:

```python
"""Configuration management - reads/writes config.json in %LOCALAPPDATA%\\TrayForge\\"""
```

Replace the data directory path in `get_data_dir()`:

```python
data_dir = os.path.join(local_appdata, "TrayForge")
```

- [ ] **Step 2: Update logger.py**

In `src/logger.py`, update `_get_log_dir()`:

```python
log_dir = os.path.join(local_appdata, "TrayForge", "logs")
```

Update `get_process_logger()` logger name:

```python
return _create_logger(f"trayforge.process.{safe}", f"{safe}.log")
```

Update `get_main_logger()`:

```python
_main_logger = _create_logger("trayforge.main", "trayforge.log")
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py src/logger.py
git commit -m "feat: rename data/log paths from AIRobotUI to TrayForge"
```

---

### Task 2: Rename src/main.pyw (entry point strings)

**Files:**
- Modify: `src/main.pyw`

- [ ] **Step 1: Update main.pyw**

Replace all `AIRobotUI` occurrences:

Docstring (line 1):
```python
"""TrayForge - tray controller for managed processes."""
```

Messagebox (line ~24):
```python
tkinter.messagebox.showwarning("TrayForge", "TrayForge is already running.")
```

Log message (line ~27):
```python
logger.info("TrayForge starting...")
```

Log message (line ~117):
```python
logger.info("TrayForge exited")
```

Also update the logger name in cleanup (line ~128):
```python
for lg_name in ("trayforge.main",):
```

- [ ] **Step 2: Commit**

```bash
git add src/main.pyw
git commit -m "feat: rename entry point strings to TrayForge"
```

---

### Task 3: Rename src/single_instance.py and src/startup.py (system identifiers)

**Files:**
- Modify: `src/single_instance.py`
- Modify: `src/startup.py`

- [ ] **Step 1: Update single_instance.py**

Replace the mutex name:

```python
MUTEX_NAME = "Global\\TrayForge_SingleInstance"
```

- [ ] **Step 2: Update startup.py**

Replace the registry value name:

```python
REG_VALUE_NAME = "TrayForge"
```

- [ ] **Step 3: Commit**

```bash
git add src/single_instance.py src/startup.py
git commit -m "feat: rename mutex and registry key to TrayForge"
```

---

### Task 4: Rename UI strings (tray, main window, config dialog)

**Files:**
- Modify: `src/tray_ui.py`
- Modify: `src/main_window.py`
- Modify: `src/config_ui.py`

- [ ] **Step 1: Update tray_ui.py**

Replace the pystray Icon name and tooltip:

```python
self._icon = pystray.Icon(
    "TrayForge",
    get_red_icon(),
    "TrayForge",
    menu=self._build_menu(),
)
```

- [ ] **Step 2: Update main_window.py**

Replace taskbar AppUserModelID:

```python
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TrayForge")
```

Replace window title:

```python
self.root.title("TrayForge - Process Control")
```

- [ ] **Step 3: Update config_ui.py**

Replace dialog title:

```python
self.dialog.title("TrayForge - Settings")
```

- [ ] **Step 4: Commit**

```bash
git add src/tray_ui.py src/main_window.py src/config_ui.py
git commit -m "feat: rename UI strings to TrayForge"
```

---

### Task 5: Rename build configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `build.bat`
- Rename: `AIRobotUI.spec` → `TrayForge.spec` (modify contents)

- [ ] **Step 1: Update pyproject.toml**

Replace project name:

```toml
name = "trayforge"
```

- [ ] **Step 2: Update AIRobotUI.spec and rename**

Replace exe name:

```python
name='TrayForge',
```

Replace runtime_tmpdir:

```python
runtime_tmpdir='%LOCALAPPDATA%/TrayForge/runtime',
```

Rename the file:

```bash
mv AIRobotUI.spec TrayForge.spec
```

- [ ] **Step 3: Update build.bat**

Replace exe name references:

```batch
echo Building TrayForge...
uv run pyinstaller --onefile --windowed --clean --name TrayForge --icon assets/icon.ico --runtime-tmpdir "%%LOCALAPPDATA%%\TrayForge\runtime" --hidden-import pystray --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw --add-data "assets/icon.ico;assets" src/main.pyw
echo.
if exist "dist\TrayForge.exe" (
    echo Build successful: dist\TrayForge.exe
) else (
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml build.bat TrayForge.spec
git rm AIRobotUI.spec 2>/dev/null; git add -u AIRobotUI.spec 2>/dev/null
git commit -m "feat: rename build config to TrayForge"
```

---

### Task 6: Rename launcher script

**Files:**
- Rename: `airobotui.bat` → `trayforge.bat`

- [ ] **Step 1: Rename the file**

```bash
mv airobotui.bat trayforge.bat
```

No internal content changes needed — it references `src/main.pyw` relatively.

- [ ] **Step 2: Commit**

```bash
git add trayforge.bat
git rm airobotui.bat 2>/dev/null; git add -u airobotui.bat 2>/dev/null
git commit -m "feat: rename launcher script to trayforge.bat"
```

---

### Task 7: Rename CI/CD workflows

**Files:**
- Modify: `.github/workflows/release.yml`
- (`.github/workflows/format-check.yml` has no project-name references — skip)

- [ ] **Step 1: Update release.yml**

Replace `AIRobotUI` references in the build step and release step:

Build step (line ~49):
```yaml
- run: uv run python -m PyInstaller --onefile --windowed --clean --name TrayForge --icon assets/icon.ico --runtime-tmpdir "%LOCALAPPDATA%/TrayForge/runtime" src/main.pyw
```

Release step — `files:` (line ~54):
```yaml
files: dist/TrayForge.exe
```

Release step — `name:` (line ~56):
```yaml
name: TrayForge ${{ steps.changelog.outputs.tag }}
```

- [ ] **Step 2: Verify format-check.yml needs no changes**

Open `.github/workflows/format-check.yml` — it has no project-name references. Skip.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "feat: rename CI release workflow to TrayForge"
```

---

### Task 8: Rename documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/specs/*.md` (titles only)
- Modify: `docs/superpowers/plans/*.md` (titles only)

- [ ] **Step 1: Update README.md**

Replace all occurrences:
- Title: `# TrayForge`
- Description line 1: `Windows 系统托盘应用，通用进程管理器...`
- Badge URL: change `AIRobotUI` in the GitHub URL to `TrayForge`
- All code blocks/examples referencing `AIRobotUI.exe`, `AIRobotUI` paths
- Project structure tree
- Configuration path: `%LOCALAPPDATA%\TrayForge\config.json`
- Log path: `%LOCALAPPDATA%\TrayForge\logs\`
- Log filename: `trayforge.log`

- [ ] **Step 2: Update AGENTS.md**

Replace title and all project name references:
- `# TrayForge 项目经验教训`
- Any `AIRobotUI` in body text

- [ ] **Step 3: Update spec/plan document titles**

For each file in `docs/superpowers/specs/` and `docs/superpowers/plans/`, update only the title line (first `#` heading) if it contains `AIRobotUI`. Body content is historical — leave as-is.

Only 4 files have "AIRobotUI" in their title — update each:

- `docs/superpowers/specs/2026-05-16-airobotui-refactor-design.md`:
  `# AIRobotUI 架构重构设计文档` → `# TrayForge 架构重构设计文档`
- `docs/superpowers/specs/2026-05-16-qqrobot-process-controller-design.md`:
  `# AIRobotUI 进程控制器设计文档` → `# TrayForge 进程控制器设计文档`
- `docs/superpowers/plans/2026-05-16-airobotui-implementation.md`:
  `# AIRobotUI Implementation Plan` → `# TrayForge Implementation Plan`
- `docs/superpowers/plans/2026-05-16-airobotui-refactor.md`:
  `# AIRobotUI Refactor Implementation Plan` → `# TrayForge Refactor Implementation Plan`

All other spec/plan files have no AIRobotUI in their title — skip.

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md docs/
git commit -m "feat: rename documentation to TrayForge"
```

---

### Task 9: Verify — ruff format and check

**Files:** (none — verification only)

- [ ] **Step 1: Run ruff format**

```bash
uv run ruff format src/
```

Expected: formats source files, no errors.

- [ ] **Step 2: Run ruff check**

```bash
uv run ruff check src/
```

Expected: 0 errors.

---

### Task 10: Rename parent directory

- [ ] **Step 1: Rename the project directory**

From the parent directory (`D:/Projects/Program/`):

```bash
mv AIRobotUI TrayForge
```

Note: this must be done from outside the AIRobotUI directory since it's the current working directory.

- [ ] **Step 2: Manual verification — launch the app**

Run:
```bash
uv run python src/main.pyw
```

Verify:
- Window title shows "TrayForge - Process Control"
- Tray tooltip shows "TrayForge"
- Settings dialog title shows "TrayForge - Settings"
- Data directory created at `%LOCALAPPDATA%\TrayForge\`
- Logs written to `%LOCALAPPDATA%\TrayForge\logs\trayforge.log`
- Single-instance mutex prevents duplicate launch
- Double-clicking `trayforge.bat` launches the app

- [ ] **Step 3: Commit**

N/A — directory rename is a filesystem operation, not tracked in git.
