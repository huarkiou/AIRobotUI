# AIRobotUI 进程控制器设计文档

## 概述

一个 Windows 系统托盘应用，用于控制和管理两个后台进程的启停：
- **NapCat QQ**：QQ 机器人协议端
- **AstrBot**：QQ 机器人逻辑端

支持独立启停、一键全控、崩溃自动重启、托盘通知、可配置化路径、开机自启、双 Tab 进程输出实时查看、日志文件记录，最终打包为单个轻量 EXE。

## 架构

```
AIRobotUI/                                      ← 项目源码目录
├── main.pyw                                    # 入口文件
├── airobotui.bat                               # 开发用启动器
├── config.py                                   # 配置管理
├── config_ui.py                                # 配置窗口（tkinter 对话框）
├── startup.py                                  # 开机自启管理（注册表）
├── logger.py                                   # 日志模块（RotatingFileHandler）
├── process_mgr.py                              # 进程管理器：启停、监控、重启、输出捕获
├── main_window.py                              # 主窗口：双 Tab 输出面板
├── tray_ui.py                                  # 托盘菜单和图标状态切换
├── icon.py                                     # 动态生成托盘图标（绿/黄/红）
├── pyproject.toml                              # uv 项目配置
├── build.bat                                   # 打包脚本（PyInstaller）
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-16-airobotui-process-controller-design.md

%LOCALAPPDATA%\AIRobotUI\                       ← 用户数据目录（运行时使用）
├── config.json                                 ← 配置文件
└── logs\                                       ← 日志目录
    ├── airobotui.log                           ← 主日志
    ├── napcat.log                              ← NapCat stdout 日志
    └── astrbot.log                             ← AstrBot stdout 日志
```

## 数据目录

- 路径：`os.path.join(os.environ["LOCALAPPDATA"], "AIRobotUI")`
- 实际路径示例：`C:\Users\<用户名>\AppData\Local\AIRobotUI\`
- 选择 `%LOCALAPPDATA%` 而非 `%APPDATA%`：进程路径是机器相关的，不需要跨机器漫游
- 运行时自动创建，无需用户手动建立

## 模块职责

### config.py
- 配置读写位置：`%LOCALAPPDATA%\AIRobotUI\config.json`
- JSON 格式：
```json
{
  "napcat": {
    "cwd": "D:\\Apps\\ai\\napcatqq\\NapCat.44498.Shell",
    "cmd": "napcat.quick.bat"
  },
  "astrbot": {
    "cwd": "D:\\Apps\\ai\\astrbot",
    "cmd": "astrbot run"
  },
  "autostart": false
}
```
- `get_data_dir()` — 返回用户数据目录路径，不存在则创建
- `load_config()` — 从数据目录读取 config.json，不存在则返回 None
- `save_config(config)` — 写入 config.json 到数据目录
- `get_default_config()` — 返回上述默认值

### logger.py
- 日志写入位置：`%LOCALAPPDATA%\AIRobotUI\logs\`
- 基于 Python 内置 `logging` 模块
- `RotatingFileHandler`：单文件最大 1MB，保留 3 个历史文件
- 日志级别：INFO
- 日志格式：`[2026-05-16 20:00:00] [INFO] message`
- 三个独立 logger：
  - `get_main_logger()` → `logs/airobotui.log` — 主日志
  - `get_napcat_logger()` → `logs/napcat.log` — NapCat 输出
  - `get_astrbot_logger()` → `logs/astrbot.log` — AstrBot 输出
- 日志目录首次写入时自动创建
- 记录内容：
  - 主日志：应用启动/退出、配置变更、进程启停命令、崩溃检测、自动重启、错误
  - 进程日志：进程 stdout/stderr 输出行

### config_ui.py
- 基于 tkinter 的配置对话框（`tk.Toplevel`）
- 两个进程配置组：NapCat（工作目录 + 启动命令）、AstrBot（工作目录 + 启动命令）
- 每个路径旁有「浏览...」按钮，调用 `filedialog.askdirectory()`
- 「开机自启」复选框，保存时同步调用 `startup.py`
- 「保存」按钮：校验路径存在性，写入 config.json，通知状态更新
- 「取消」按钮：放弃修改
- 首次运行无配置时自动弹出，配置不完整不允许关闭

### startup.py
- `enable_autostart()` — 写入注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\AIRobotUI`，值为打包后 EXE 完整路径
- `disable_autostart()` — 删除上述注册表项
- `is_autostart_enabled()` — 检查注册表项是否存在
- 使用 Python 内置 `winreg` 模块

### main.pyw
- 应用入口（.pyw 无黑窗）
- 初始化日志系统
- 加载配置，若无配置则弹出 `config_ui` 阻塞等待
- 初始化 `ProcessManager`
- 创建 `MainWindow`（双 Tab 输出面板），初始隐藏
- 创建 `TrayUI`，传入各组件引用
- 进入托盘消息循环
- 退出时写日志并清理

### process_mgr.py
- 管理两个进程的生命周期
- 使用 `subprocess.Popen`，stdout/stderr 重定向到 `PIPE`
- NapCat：在配置的 cwd 下执行 cmd（shell=True）
- AstrBot：在配置的 cwd 下执行 cmd
- 输出捕获：每个进程一个独立读取线程，推送到：
  - 主窗口面板（`on_output` 回调）
  - 对应进程日志文件（`logger.py`）
- 停止策略：`terminate()` → 等 3 秒 → `kill()`
- 监控线程：每 2 秒 `poll()`，异常退出自动重启
- 重启上限：连续 3 次失败后放弃，托盘通知
- 所有启停操作写主日志
- 对外接口：
  - `start_napcat()` / `stop_napcat()` / `is_napcat_running()`
  - `start_astrbot()` / `stop_astrbot()` / `is_astrbot_running()`
  - `start_all()` / `stop_all()`
  - `update_config(config)`
  - 回调：`on_status_change(callback)` / `on_output(process_name, line)`

### main_window.py
- 基于 tkinter 顶层窗口（`tk.Tk`）
- `ttk.Notebook` 双 Tab：**NapCat** / **AstrBot**
- 每个 Tab 内：
  - `tk.Text`（只读，带滚动条）— 黑色背景绿色文字，终端风格
  - 自动滚动到最底
  - 右键菜单：「清空当前 Tab」「复制选中」
- 窗口标题：`AIRobotUI - 进程控制`
- 关闭窗口 → 隐藏到托盘（不退出）
- `append_output(process_name, line)` — 供 ProcessManager 回调调用
- 行数限制：每 Tab 最多 5000 行，超出裁剪最旧行

### tray_ui.py
- 基于 `pystray` 系统托盘
- 菜单结构：

```
🤖 AIRobotUI
├── NapCat      ● 运行中 / ○ 已停止    ← 点击切换
├── AstrBot     ● 运行中 / ○ 已停止    ← 点击切换
├── ──────────────────────
├── ▶ 全部启动
├── ⏹ 全部停止
├── ──────────────────────
├── 📋 显示窗口                       ← 打开主窗口
├── ⚙ 设置                           ← 打开配置窗口
├── ──────────────────────
├── 退出                             ← 停止所有进程后退出
```

- 双击托盘图标 → 切换主窗口显示/隐藏
- 退出时停止所有进程、写日志

### icon.py
- Pillow 生成 64×64 圆形图标
- 🟢 绿：两个都在运行 / 🟡 黄：一个在运行 / 🔴 红：两个都停止

### airobotui.bat（开发用启动器）
```bat
@echo off
uv run python main.pyw
```

### build.bat（打包脚本）
```bat
@echo off
uv run pyinstaller --onefile --windowed --clean ^
  --name AIRobotUI ^
  --add-data "icon.png;." ^
  --collect-all pystray ^
  main.pyw
```
- 输出：`dist/AIRobotUI.exe`
- 体积预估：~15-25MB

### pyproject.toml
```toml
[project]
name = "airobotui"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pystray",
    "Pillow",
    "pyinstaller",
]
```

## 数据流

```
用户操作 → tray_ui.py → process_mgr.py
                              ├── subprocess.Popen (PIPE)
                              │       └── stdout → 读取线程
                              │               ├── on_output → main_window.py (UI)
                              │               └── logger.py → %LOCALAPPDATA%\AIRobotUI\logs\
                              ├── on_status_change → tray_ui.py (图标/菜单)
                              └── logger.py (操作日志)
```

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 启动失败（路径/文件不存在） | 托盘通知 + 写日志，引导打开设置 |
| 停止超时 | force kill + 写日志 |
| 连续崩溃 3 次 | 放弃自动重启，托盘通知 + 写日志 |
| 托盘退出 | 停止所有子进程 + 写日志 |
| 首次运行无配置 | 弹出配置窗口，阻塞启动流程 |
| 配置保存失败 | 托盘通知 + 写日志 |
| 注册表写入失败 | 托盘通知 + 写日志，不影响其他功能 |
| 日志文件写入失败 | 静默忽略，不崩溃 |
| 数据目录创建失败 | 托盘通知 + 写日志，放弃运行 |

## 未纳入范围（YAGNI）

- 远程控制 / Web 面板
- 多实例管理
- 进程输出搜索/过滤
- 窗口置顶 / 最小化动画
- 自动更新
