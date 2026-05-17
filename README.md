# AIRobotUI

Windows 系统托盘应用，一键管理 NapCat QQ 和 AstrBot 两个进程的启停。

[![Format Check](https://github.com/huarkiou/AIRobotUI/actions/workflows/format-check.yml/badge.svg)](https://github.com/huarkiou/AIRobotUI/actions/workflows/format-check.yml)

## 功能

- 托盘图标，右键菜单控制
- 独立启停 / 一键全控 NapCat 和 AstrBot
- 进程运行时自动显示 **Open WebUI** 按钮，一键打开浏览器
- 双 Tab 实时查看进程输出
- 进程崩溃自动重启（最多 3 次）
- 可配置进程路径、编码、开机自启
- 日志文件记录（启动/停止/崩溃/输出）
- 单实例运行保护

## 系统要求

- Windows 10+
- Python 3.11+（开发）/ 直接运行 `AIRobotUI.exe`（发布版）

## 快速开始

### 开发运行

```bash
git clone <repo>
cd AIRobotUI
uv sync
uv run python src/main.pyw
```

或双击 `airobotui.bat`。

### 打包

```bash
uv sync
build.bat
# 输出：dist/AIRobotUI.exe
```

## 项目结构

```
AIRobotUI/
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

1. 双击 `AIRobotUI.exe`，托盘出现红色图标
2. 首次运行弹出设置，确认 NapCat 和 AstrBot 路径后保存
3. 右键托盘 → **NapCat** / **AstrBot** 切换启停
4. 进程运行后，子菜单出现 **Open WebUI** → 一键打开浏览器管理面板
5. **Show/Hide Window** 打开输出面板查看日志
6. **Start All** / **Stop All** 一键全控
7. **Exit** 优雅退出（自动终止所有进程）

## 配置

配置文件位于 `%LOCALAPPDATA%\AIRobotUI\config.json`：

```json
{
  "napcat": {
    "cwd": "D:\\Apps\\ai\\AIRobotUI\\napcatqq\\NapCat.44498.Shell",
    "cmd": "NapCatWinBootMain.exe 2450085301",
    "encoding": "utf-8"
  },
  "astrbot": {
    "cwd": "D:\\Apps\\ai\\AIRobotUI\\astrbot",
    "cmd": "astrbot run",
    "encoding": "utf-8"
  },
  "output_refresh_ms": 500,
  "autostart": false
}
```

也可通过托盘菜单 → **Settings** 图形化配置。

## 日志

日志位于 `%LOCALAPPDATA%\AIRobotUI\logs\`：
- `airobotui.log` — 应用操作日志
- `napcat.log` — NapCat 进程输出
- `astrbot.log` — AstrBot 进程输出
