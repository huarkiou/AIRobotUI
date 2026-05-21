# Singleton/Cleanup Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `singleton`'s dual role into `singleton` (prevent duplicate self) + `cleanup_cwd` (kill same-cwd processes), so same-cwd processes don't kill each other.

**Architecture:** Add `cleanup_cwd: bool` to `ProcessConfig`, default `false`. `_start()` uses `cleanup_cwd` to gate `_kill_cwd_processes`; `singleton` only gates the `is_running` check. Old configs auto-migrate: if `singleton` was `true` and `cleanup_cwd` missing, set `cleanup_cwd: true`.

**Tech Stack:** Python 3.11+, uv, ruff

---

### Task 1: Core logic — types + process_mgr + config migration

**Files:**
- Modify: `src/trayforge_types.py`
- Modify: `src/process_mgr.py`
- Modify: `src/config.py`

- [ ] **Step 1: Add cleanup_cwd to ProcessConfig**

In `src/trayforge_types.py`:

```python
class ProcessConfig(TypedDict):
    name: str
    cwd: str
    cmd: str
    encoding: str
    singleton: bool
    autostart: bool
    cleanup_cwd: bool
    webui_pattern: str | None
    delete_before_start: list[str]
```

- [ ] **Step 2: Split singleton logic in _start()**

In `src/process_mgr.py`, find the singleton block in `_start()`:

```python
        # Singleton: kill all processes matching cwd
        if singleton and sys.platform == "win32":
            self._kill_cwd_processes(cwd)
```

Replace with:

```python
        # Cleanup cwd: kill all processes matching cwd (for processes that leave zombies)
        cleanup = cfg.get("cleanup_cwd", singleton)  # migrate: old singleton=true → cleanup=true
        if cleanup and sys.platform == "win32":
            self._kill_cwd_processes(cwd)
```

- [ ] **Step 3: Add config migration for old singleton configs**

In `src/config.py`, `get_default_config()`, add `"cleanup_cwd"` to each default process. Also update `_migrate_old_config()` to set `cleanup_cwd` when `singleton` was `true`.

In `get_default_config()`, add to each process dict:

```python
                "cleanup_cwd": False,
```

In `_migrate_old_config()`, in the loop after setting `"singleton": True`:

```python
                    "cleanup_cwd": True,
```

- [ ] **Step 4: Run ruff, run existing tests**

```bash
uv run ruff format src/ && uv run ruff check src/ && uv run pytest tests/ -v
```

Expected: 29 passed, 0 ruff errors.

- [ ] **Step 5: Commit**

```bash
git add src/trayforge_types.py src/process_mgr.py src/config.py
git commit -m "feat: add cleanup_cwd field, split from singleton"
```

---

### Task 2: Settings UI — add cleanup_cwd checkbox

**Files:**
- Modify: `src/config_ui.py`

- [ ] **Step 1: Add defaults and checkbox for cleanup_cwd**

In `_add_process()` method (defaults dict), add:

```python
            "cleanup_cwd": False,
```

After the `singleton`/`autostart` checkbox row, add a new row for `cleanup_cwd`:

```python
        # Row 4.5: Cleanup CWD
        v["cleanup_cwd"] = tk.BooleanVar(value=defaults["cleanup_cwd"])
        ttk.Checkbutton(
            check_frame, text="Cleanup CWD", variable=v["cleanup_cwd"]
        ).pack(side=tk.LEFT, padx=(0, 10))
```

In `_load_current_config()`, add `cleanup_cwd` to defaults passed to `_add_process`:

```python
                    "cleanup_cwd": proc.get("cleanup_cwd", False),
```

In `_on_save()`, add `cleanup_cwd` to the saved process dict:

```python
                "cleanup_cwd": v["cleanup_cwd"].get(),
```

- [ ] **Step 2: Run ruff, run tests**

```bash
uv run ruff format src/ && uv run ruff check src/ && uv run pytest tests/ -v
```

Expected: 29 passed, 0 ruff errors.

- [ ] **Step 3: Commit**

```bash
git add src/config_ui.py
git commit -m "feat: add cleanup_cwd checkbox to settings"
```

---

### Task 3: Update docs and user config

**Files:**
- Modify: `README.md`
- Modify: user config `%LOCALAPPDATA%\TrayForge\config.json`

- [ ] **Step 1: Update README process config field table**

Add row after `singleton`:

```
| `cleanup_cwd` | 启动前杀同工作目录的所有进程（默认 false），用于清理僵尸进程 |
```

- [ ] **Step 2: Update user config with proper cleanup_cwd values**

```bash
uv run python -c "
import json, os
path = os.path.join(os.environ['LOCALAPPDATA'], 'TrayForge', 'config.json')
with open(path) as f:
    config = json.load(f)
for p in config['processes']:
    p['cleanup_cwd'] = p['name'] in ('NapCat', 'AstrBot')
    p['singleton'] = True
with open(path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print('Updated config:')
for p in config['processes']:
    print(f\"  {p['name']}: singleton={p['singleton']}, cleanup_cwd={p['cleanup_cwd']}\")
"
```

Expected: NapCat/AstrBot has `cleanup_cwd: true`; Llama/Embedding has `cleanup_cwd: false`; all `singleton: true`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document cleanup_cwd field"
```
