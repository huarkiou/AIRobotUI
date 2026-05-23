# TrayForge

Windows 系统托盘应用，通用进程管理器，一键管理 NapCat QQ、AstrBot、llama.cpp 等多个后台进程。

[![Format Check](https://github.com/huarkiou/TrayForge/actions/workflows/format-check.yml/badge.svg)](https://github.com/huarkiou/TrayForge/actions/workflows/format-check.yml)

## 功能

- 托盘图标，右键菜单控制（绿/黄/红 三色指示）
- 通用进程管理，支持添加任意后台进程（NapCat、AstrBot、llama.cpp 等）
- 每进程独立启停
- 进程运行时自动显示其 WebUI URL 在子菜单中，一键打开浏览器
- **CLI 命令行控制**：`TrayForge.exe list/start/stop/status/reload` 等命令，无需打开 GUI
- **headless 后台模式**：`TrayForge.exe --headless` 纯后台运行，适合服务器/CI
- **Reload Config** 运行时重载配置，无需重启
- 动态 Tab 实时查看每个进程的输出
- 进程崩溃自动重启（60s 冷却，最多 3 次）
- Settings 图形化配置：添加/删除/编辑进程，全局参数调整
- 每进程独立日志文件
- 开机自启（主程序 + 每进程独立控制）
- 单实例运行保护

## 系统要求

- Windows 10+
- Python 3.11+（开发）/ 直接运行 `TrayForge.exe`（发布版）

## 快速开始

### 开发运行

```bash
git clone <repo>
cd TrayForge
uv sync
uv run python src/main.pyw
```

或双击 `trayforge.bat`。

### 打包

```bash
uv sync
build.bat
# 输出：dist/TrayForge.exe
```

## 项目结构

```
TrayForge/
├── .github/workflows/      # CI/CD
│   ├── format-check.yml    # 代码格式检查
│   └── release.yml         # 手动发布 exe
├── src/                    # 源码
│   ├── main.pyw            # 入口（无参=GUI，有参=CLI，--headless=后台）
│   ├── app_controller.py   # 应用控制器（GUI 事件循环、action 分发）
│   ├── headless_controller.py # 后台模式控制器（Queue 事件循环）
│   ├── config.py           # 配置读写
│   ├── config_ui.py        # 设置对话框
│   ├── process_mgr.py      # 进程管理器
│   ├── http_server.py      # HTTP 服务端（CLI 通信）
│   ├── cli.py              # CLI 命令行参数解析与 HTTP 客户端
│   ├── tray_ui.py          # 系统托盘
│   ├── main_window.py      # 主窗口（输出面板）
│   ├── logger.py           # 日志模块
│   ├── icon.py             # 托盘图标生成
│   ├── startup.py          # 开机自启
│   ├── single_instance.py  # 单实例保护
│   └── trayforge_types.py  # 类型定义（ProcessConfig, AppConfig, ProcessStatus）
├── assets/                 # 静态资源
│   └── icon.ico
├── tests/                  # 测试（79 tests）
├── docs/                   # 设计文档
├── pyproject.toml
├── build.bat
└── README.md
```

## 使用说明

1. 双击 `TrayForge.exe`，托盘出现红色图标
2. 首次运行弹出设置，确认 NapCat 和 AstrBot 路径后保存
3. 右键托盘 → **NapCat** / **AstrBot** 切换启停
4. 进程运行后，子菜单显示其 WebUI URL → 一键打开浏览器
5. **Show Window** 打开输出面板查看日志
6. **Reload Config** 运行时从磁盘重载配置文件
7. **Exit** 优雅退出（自动终止所有进程）

> 启动失败时（路径不存在、命令为空等），错误信息会显示在主窗口的输出面板中，方便排查。

### CLI 命令行

同一个 `TrayForge.exe` 支持命令行模式（需先启动 GUI 实例）：

```bash
TrayForge.exe list              # 列出所有进程及状态
TrayForge.exe status NapCat     # 查看 NapCat 详细状态（PID、WebUI、重启次数）
TrayForge.exe start NapCat      # 启动 NapCat
TrayForge.exe stop NapCat       # 停止 NapCat
TrayForge.exe restart NapCat    # 重启 NapCat
TrayForge.exe webui NapCat      # 打印 NapCat WebUI URL
TrayForge.exe reload            # 通知 GUI 从磁盘重载配置
TrayForge.exe --help            # 查看帮助
```

CLI 通过本地 HTTP (`127.0.0.1:<port>`) 与实例通信，无需额外配置。

### headless 后台模式

无需桌面环境，纯后台运行 ProcessManager + HTTP 服务：

```bash
TrayForge.exe --headless    # 启动后台服务
TrayForge.exe list           # 另一个终端查看状态
# Ctrl+C 退出
```

### 环境变量

| 变量 | 说明 |
|---|---|
| `TRAYFORGE_DATA_DIR` | 覆盖数据目录（默认 `%LOCALAPPDATA%\TrayForge`），设置后 `config.json`、日志等均写入新目录 |

## 配置

配置文件位于 `%LOCALAPPDATA%\TrayForge\config.json`（旧格式自动迁移）：

```json
{
  "processes": [
    {
      "name": "NapCat",
      "cwd": "D:\\path\\to\\napcat",
      "cmd": "NapCatWinBootMain.exe <your-qq>",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
      "cleanup_cwd": true,
      "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?://\\S+)",
      "delete_before_start": []
    },
    {
      "name": "AstrBot",
      "cwd": "D:\\path\\to\\astrbot",
      "cmd": "astrbot run",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
      "cleanup_cwd": true,
      "webui_pattern": "Starting WebUI at (https?://\\S+)",
      "delete_before_start": ["astrbot.lock"]
    }
  ],
  "output_refresh_ms": 500,
  "poll_interval_ms": 2000,
  "autostart": false
}
```

也可通过托盘菜单 → **Settings** 图形化配置（添加/删除/编辑进程）。

### 进程配置字段

| 字段 | 说明 |
|---|---|
| `name` | 进程显示名（唯一） |
| `cwd` | 工作目录，空则用当前目录 |
| `cmd` | 完整命令行，二进制支持绝对路径或 PATH 搜索 |
| `singleton` | 单例模式，防止同进程名重复启动 |
| `autostart` | 随 TrayForge 启动自动拉起 |
| `cleanup_cwd` | 启动前杀同工作目录的残留进程，用于清理僵尸进程 |
| `webui_pattern` | 正则，捕获组提取 WebUI URL；留空则无 WebUI 菜单 |
| `delete_before_start` | 启动前删除的文件列表（相对 cwd），被占用时杀占用进程 |

## 日志

日志位于 `%LOCALAPPDATA%\TrayForge\logs\`：
- `trayforge.log` — 应用操作日志
- `<进程名>.log` — 每进程独立日志（如 `NapCat.log`、`AstrBot.log`、`Llama.log`）
