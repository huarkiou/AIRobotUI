# TrayForge 内部质量改进

Date: 2026-05-21  
Type: 重构 — 测试、结构拆分、类型、异常、校验、错误提示

## 目标

改进代码内部质量和可维护性，零功能变更，为用户可见功能迭代打好基础。

## 改动项

按建议顺序排列（先小改、再拆分、最后补测试）：

### 3. 收紧异常处理

**文件：** `src/process_mgr.py`

移除无声吞异常，至少记日志：

| 位置 | 当前 | 改为 |
|---|---|---|
| `_emit_status()` | `except Exception: pass` | `except Exception: logger.warning("status listener failed", exc_info=True)` |
| `_notify()` | `except Exception: pass` | `except Exception: logger.warning("notification listener failed", exc_info=True)` |
| `_kill_cwd_processes()` 内层 | `except (NoSuchProcess, AccessDenied, Exception): pass` | `except (NoSuchProcess, AccessDenied): pass` + `except Exception: logger.debug(...)` |
| `main_window.destroy()` | `except Exception: pass` | 保持（tkinter destroy 不可预测） |
| 其他异常捕获 | — | 已精确，不动 |

### 4. 补充类型注解

**新增文件：** `src/types.py`  
**修改文件：** `src/config.py`, `src/process_mgr.py`, `src/tray_ui.py`, `src/config_ui.py`

新增两个 TypedDict：

```python
class ProcessConfig(TypedDict):
    name: str
    cwd: str
    cmd: str
    encoding: str
    singleton: bool
    autostart: bool
    webui_pattern: str | None
    delete_before_start: list[str]

class AppConfig(TypedDict):
    processes: list[ProcessConfig]
    output_refresh_ms: int
    poll_interval_ms: int
    autostart: bool
```

各模块中 `dict` → `ProcessConfig` 或 `AppConfig`，`callable` → 具体签名：

| 文件 | 类型更改 |
|---|---|
| `config.py` | `load_config() -> AppConfig \| None`; `save_config(config: AppConfig) -> bool`; `_migrate_old_config(old: dict) -> AppConfig` |
| `process_mgr.py` | `__init__(config: AppConfig)`; `_build_from_config(config: AppConfig)`; `update_config(config: AppConfig)`; `_ProcState.cfg: ProcessConfig` |
| `tray_ui.py` | `TrayUI.__init__(config: AppConfig)`; `set_config_callback(cb: Callable[[], None])`; `consume_action() -> str \| None` |
| `config_ui.py` | `get_result() -> AppConfig \| None` |
| `app_controller.py` | `AppController.__init__(config: AppConfig)` |

### 6. 错误提示覆盖面

**文件：** `src/process_mgr.py`

`_start()` 中 `delete_before_start` 两个失败路径加 `_system_msg`：

- 权限不足重试后仍删除失败 → `_system_msg(name, f"Failed to delete {rel_path}: {e}")`
- 路径逃逸 cwd → `_system_msg(name, f"Skipped delete {rel_path}: path outside cwd")`

### 5. 配置校验

**文件：** `src/config_ui.py`

在 `_validate()` 方法中新增两项校验：

1. `name` 不含路径分隔符 `/` 或 `\`
2. `webui_pattern` 若非空，用 `re.compile()` 试编译，失败则报 `"Invalid regex for '{name}': {error}"`
3. `cwd` 存在性检查从 `return error`（阻塞保存）改为 `logger.warning()`（允许保存，用户可能先配置后创建目录）

校验失败用 `messagebox.showerror` 提示，包含进程名和字段名。

### 2. 拆分 main.pyw

**新增文件：** `src/app_controller.py`  
**修改文件：** `src/main.pyw`

抽 `AppController` 类，职责：事件循环、action dispatch、输出缓冲、自动启动、清理。接口保持与现有 `TrayUI`/`MainWindow`/`ProcessManager` 的协作方式不变。

`main.pyw` 简化为入口函数（~25 行），只做初始化、创建 `AppController`、调用 `start()`。

```python
class AppController:
    def __init__(self, config, pm, window, tray): ...
    def start(self): ...
    def _tick(self): ...
    def _setup_first_run(self): ...
    def _autostart(self): ...
    def _cleanup(self): ...
```

### 1. 补测试

**新增文件：** `tests/test_process_mgr.py`, `tests/test_config.py`, `tests/test_logger.py`  
**依赖：** `pytest` (dev)

| 测试文件 | 覆盖内容 |
|---|---|
| `test_process_mgr.py` | `_build_from_config` 增删改进程；`start`/`stop`/`start_all`/`stop_all` 状态；`poll_crashes` 冷却/次数限制；`_system_msg` 注入；`drain` 清空队列 |
| `test_config.py` | `get_default_config` 结构；`_migrate_old_config`；`load_config` 文件存在/不存在/损坏；`save_config` 写入 |
| `test_logger.py` | `get_process_logger` 名称过滤；`get_main_logger` 单例 |

测试方式：mock `subprocess.Popen`、`threading.Thread`、`psutil.process_iter`，使用 `tmp_path` 临时文件。

## 不涉及

- 无功能变更
- 不改 UI
- 不改构建配置
- 不改 CI/CD
