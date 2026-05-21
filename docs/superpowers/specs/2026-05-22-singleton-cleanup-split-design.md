# Singleton 拆分：separate cleanup_cwd from singleton

Date: 2026-05-22  
Type: 微重构，零功能变更（向后兼容）

## 问题

`singleton: true` 同时做两件事：防自身重复启动 + `_kill_cwd_processes` 杀同 cwd 所有进程。当同 cwd 下有多个进程（如 llama-server 不同端口），两两互杀。

## 方案

拆分 `singleton` 的双重职责，新增 `cleanup_cwd` 字段：

| 字段 | 类型 | 默认 | 作用 |
|---|---|---|---|
| `singleton` | bool | false | 防自身重复启动（仅此一事） |
| `cleanup_cwd` | bool | false | 启动前杀同 cwd 所有进程 |

**行为变化：**

- `singleton: true` → `_start()` 仅检查 `is_running(name)`，若已运行则 return（不杀任何进程）
- `cleanup_cwd: true` → `_start()` 调 `_kill_cwd_processes(cwd)`（原 `singleton` 的杀进程行为）
- 两者可独立设置

**向后兼容：** 配置文件自动迁移——遇旧格式 `singleton: true` 且无 `cleanup_cwd` 字段时，同时设 `cleanup_cwd: true`。

**推荐配置：**

| 进程 | singleton | cleanup_cwd |
|---|---|---|
| NapCat | true | true |
| AstrBot | true | true |
| Llama | true | false |
| Embedding | true | false |

**改动点：**

- `trayforge_types.py`：`ProcessConfig` 加 `cleanup_cwd: bool`
- `process_mgr.py`：`_start()` 拆分 `singleton` 检查和 `cleanup_cwd` 调用
- `config.py`：旧配置迁移加 `cleanup_cwd` 字段
- `config_ui.py`：Settings 面板 `singleton` checkbox 旁加 `cleanup_cwd` checkbox
- `README.md`：字段表加 `cleanup_cwd` 说明
