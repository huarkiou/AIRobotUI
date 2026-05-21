# TrayForge

Windows 系统托盘应用，通用进程管理器，一键管理 NapCat QQ、AstrBot、llama.cpp 等多个后台进程。

[![Format Check](https://github.com/huarkiou/TrayForge/actions/workflows/format-check.yml/badge.svg)](https://github.com/huarkiou/TrayForge/actions/workflows/format-check.yml)

## 功能

- 托盘图标，右键菜单控制（绿/黄/红 三色指示）
- 通用进程管理，支持添加任意后台进程（NapCat、AstrBot、llama.cpp 等）
- 每进程独立启停 + Start All / Stop All 一键全控
- 进程运行时自动显示 **Open WebUI** 按钮（如有），一键打开浏览器
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
│   ├── main.pyw            # 入口
│   ├── config.py           # 配置读写
│   ├── config_ui.py        # 设置对话框
│   ├── process_mgr.py      # 进程管理器
│   ├── tray_ui.py          # 系统托盘
│   ├── main_window.py      # 主窗口（输出面板）
│   ├── logger.py           # 日志模块
│   ├── icon.py             # 托盘图标生成
│   ├── startup.py          # 开机自启
│   └── single_instance.py  # 单实例保护
├── assets/                 # 静态资源
│   └── icon.ico
├── tests/                  # 测试（待补充）
├── docs/                   # 设计文档
├── pyproject.toml
├── build.bat
└── README.md
```

## 使用说明

1. 双击 `TrayForge.exe`，托盘出现红色图标
2. 首次运行弹出设置，确认 NapCat 和 AstrBot 路径后保存
3. 右键托盘 → **NapCat** / **AstrBot** 切换启停
4. 进程运行后，子菜单出现 **Open WebUI** → 一键打开浏览器管理面板
5. **Show/Hide Window** 打开输出面板查看日志
6. **Start All** / **Stop All** 一键全控
7. **Exit** 优雅退出（自动终止所有进程）

## 配置

配置文件位于 `%LOCALAPPDATA%\TrayForge\config.json`（旧格式自动迁移）：

```json
{
  "processes": [
    {
      "name": "NapCat",
      "cwd": "D:\\Apps\\ai\\TrayForge\\napcatqq\\NapCat.44498.Shell",
      "cmd": "NapCatWinBootMain.exe 2450085301",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
      "webui_pattern": "\\[WebUi\\] WebUi User Panel Url: (https?://\\S+)",
      "delete_before_start": []
    },
    {
      "name": "AstrBot",
      "cwd": "D:\\Apps\\ai\\TrayForge\\astrbot",
      "cmd": "astrbot run",
      "encoding": "utf-8",
      "singleton": true,
      "autostart": false,
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
| `singleton` | 单例模式，启动前杀同 cwd 的旧进程 |
| `autostart` | 随 TrayForge 启动自动拉起 |
| `webui_pattern` | 正则，捕获组提取 WebUI URL；留空则无 WebUI 菜单 |
| `delete_before_start` | 启动前删除的文件列表（相对 cwd），被占用时杀占用进程 |

## 日志

日志位于 `%LOCALAPPDATA%\TrayForge\logs\`：
- `trayforge.log` — 应用操作日志
- `<进程名>.log` — 每进程独立日志（如 `NapCat.log`、`AstrBot.log`、`Llama.log`）
