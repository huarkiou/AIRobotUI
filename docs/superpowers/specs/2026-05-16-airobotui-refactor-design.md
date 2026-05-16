# AIRobotUI 架构重构设计文档

## 概述

重构 AIRobotUI 的线程模型，消除当前 6 线程互相争抢 `Popen` 对象导致的进程管理不可靠、退出卡死等问题。同时增加单实例运行保护。

## 核心变化

### 线程模型：6 → 3

```
之前:
  tkinter 主线程
  pystray daemon 线程
  monitor 线程          ← 删除
  2× reader 线程
  toggle/stop/start 线程 ← 删除
  exit 线程              ← 删除

之后:
  tkinter 主线程        ← 所有 Popen 操作在此线程
  pystray daemon 线程   ← 只负责托盘 UI
  2× reader 线程        ← 只从 pipe 读行 → 丢 queue.Queue
```

### 线程职责边界

| 线程 | 允许操作 | 禁止操作 |
|------|---------|---------|
| **主线程** | `Popen.terminate()` `Popen.wait()` `Popen.poll()` `Queue.get_nowait()` 所有 tkinter | 长时间阻塞（>1s 用子线程） |
| **pystray** | `icon.*` API | 任何 Popen 操作、tkinter 操作 |
| **reader** | `pipe.readline()` `Queue.put()` 写日志文件 | 任何 Popen 操作、tkinter 操作 |

### 事件循环

```
main.pyw._tick() 每 100ms 执行:
  1. consume_action()     — 从托盘队列取待执行操作
  2. drain_output()       — 从 Queue 取 reader 输出 → 推面板
  3. poll_crashes()       — 每 2s 一次，检查进程是否崩溃
  4. exit_check()         — 检查退出标记
```

### Exit 流程（全部在主线程）

```
_tick() 检测到 _exit_requested:
  ├── window.hide()       — 窗口立刻消失
  ├── pm.shutdown()       — 同步杀进程（阻塞 ~15s）
  └── root.quit()         — 退出 mainloop

mainloop 退出后:
  └── window.destroy()    — 清理 tkinter
```

### 单实例保护

- Windows 命名 Mutex `Global\AIRobotUI_SingleInstance`
- 启动时 `CreateMutexW` 检查，已存在则弹窗提示并退出

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `single_instance.py` | **新建** | 命名 mutex 单例检查 |
| `process_mgr.py` | **重写** | 去 monitor 线程，加 Queue 输出，`poll_crashes()` 供主线程调用 |
| `tray_ui.py` | **重写** | 去后台线程，`_pending_action` 字符串队列，`consume_action()` 供主线程取 |
| `main.pyw` | **重写** | 统一 `_tick()` 事件循环，单实例检查 |
| `main_window.py` | 不变 | 已有 `append_output` 线程安全 |
| `config.py` `config_ui.py` `logger.py` `icon.py` `startup.py` | 不变 | — |

## process_mgr 新接口

```python
class ProcessManager:
    # 启动/停止（主线程调用，同步）
    start_napcat() / stop_napcat()
    start_astrbot() / stop_astrbot()
    start_all() / stop_all()
    is_napcat_running() -> bool
    is_astrbot_running() -> bool

    # 主线程轮询
    poll_crashes()           # 检查崩溃，必要时自动重启
    drain_napcat() -> list   # 取 NapCat 输出行
    drain_astrbot() -> list  # 取 AstrBot 输出行

    # 配置和回调
    update_config(dict)
    on_status_change(cb)
    on_notification(cb)

    # 退出
    shutdown()  # 同步，阻塞 ~15s
```

## tray_ui 新接口

```python
class TrayUI:
    _exit_requested: bool       # 主线程读取
    _pending_action: str | None # 主线程 consume
    consume_action() -> str | None
```

## 未纳入范围

- 进程输出搜索/过滤
- 远程控制
- 多实例管理（已反其道而行之——禁多实例）
