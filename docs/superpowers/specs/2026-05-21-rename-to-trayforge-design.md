# Rename AIRobotUI → TrayForge

Date: 2026-05-21  
Type: Pure rename, zero functional changes

## Case mapping

| Original | New |
|---|---|
| `AIRobotUI` (PascalCase) | `TrayForge` |
| `airobotui` (lowercase) | `trayforge` |

## Scope

Every occurrence across all project files. Cached artifacts (build output, `__pycache__`, `.ruff_cache`) are excluded — they regenerate on next run.

## Files to modify

### Source code (`src/*.py`)

| File | Changes |
|---|---|
| `main.pyw` | Docstring `"AIRobotUI"` → `"TrayForge"`; messagebox title `"AIRobotUI"` → `"TrayForge"`; log message `"AIRobotUI starting..."` → `"TrayForge starting..."`; log message `"AIRobotUI exited"` → `"TrayForge exited"` |
| `config.py` | `get_data_dir()` path: `"AIRobotUI"` → `"TrayForge"`; comment in docstring |
| `tray_ui.py` | `pystray.Icon("AIRobotUI", ...)` name and tooltip → `"TrayForge"` |
| `main_window.py` | `SetCurrentProcessExplicitAppUserModelID("AIRobotUI")` → `"TrayForge"`; window title `"AIRobotUI - Process Control"` → `"TrayForge - Process Control"` |
| `config_ui.py` | Dialog title `"AIRobotUI - Settings"` → `"TrayForge - Settings"` |
| `single_instance.py` | Mutex name `"Global\\AIRobotUI_SingleInstance"` → `"Global\\TrayForge_SingleInstance"`; comment |
| `startup.py` | Registry value name `REG_VALUE_NAME = "AIRobotUI"` → `"TrayForge"` |
| `logger.py` | Logger names: `"airobotui.main"` → `"trayforge.main"`, `"airobotui.process.*"` → `"trayforge.process.*"`; log filename `"airobotui.log"` → `"trayforge.log"`; data dir `"AIRobotUI"` → `"TrayForge"`; comments |

### Build config

| File | Changes |
|---|---|
| `pyproject.toml` | `name = "airobotui"` → `"trayforge"`; `description` update optional |
| `AIRobotUI.spec` | `name='AIRobotUI'` → `name='TrayForge'`; `runtime_tmpdir` path `AIRobotUI` → `TrayForge`; rename file to `TrayForge.spec` |
| `build.bat` | Exe name references `AIRobotUI` → `TrayForge`; comment |

### Scripts

| File | Changes |
|---|---|
| `airobotui.bat` | Rename to `trayforge.bat`; internal path `src/main.pyw` unchanged (relative) |

### CI/CD (`.github/workflows/`)

| File | Changes |
|---|---|
| `format-check.yml` | Any `AIRobotUI` references → `TrayForge` |
| `release.yml` | Any `AIRobotUI` references → `TrayForge` |

### Documentation

| File | Changes |
|---|---|
| `README.md` | All `AIRobotUI`/`airobotui` references; badge URL |
| `AGENTS.md` | Title and project name references |
| `docs/superpowers/specs/*.md` | Titles only (rename references); body content is historical, leave as-is |
| `docs/superpowers/plans/*.md` | Titles only |

### Parent directory

| Item | Action |
|---|---|
| `AIRobotUI/` | Rename to `TrayForge/` |

### Not modified

- `__pycache__/`, `build/`, `dist/`, `.ruff_cache/` — regenerate on next run
- `.venv/` — virtualenv, not project content
- `_test_migration/`, `_test_migration_verify/` — test artifacts, leave as-is
- `assets/icon.ico` — unchanged

## Verification

1. Run `uv run ruff format src/ && uv run ruff check src/` — no regressions
2. Launch the app, confirm:
   - Window title shows "TrayForge - Process Control"
   - Tray tooltip shows "TrayForge"
   - Settings dialog title shows "TrayForge - Settings"
   - Data directory created at `%LOCALAPPDATA%\TrayForge\`
   - Logs written to `%LOCALAPPDATA%\TrayForge\logs\trayforge.log`
   - Single-instance mutex prevents duplicate launch
