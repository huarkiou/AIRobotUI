# AIRobotUI 项目经验教训

> 本项目为 Windows 托盘应用，管理 NapCat QQ 和 AstrBot 两个后台进程。以下为开发过程中踩过的坑和总结。

## Windows 进程管理

### 启动进程
- `subprocess.Popen` 的 `cwd` 参数**不参与可执行文件搜索**。裸文件名（如 `NapCatWinBootMain.exe`）只在 PATH 中查找。
- **修复**：启动前用 `os.path.join(cwd, exe)` 拼绝对路径，或加 `.\` 前缀。
- `CREATE_NO_WINDOW` 隐藏子进程控制台窗口。注意：给 `subprocess.run` 也要加（如 `taskkill`），否则会闪黑框。
- 设置 `PYTHONIOENCODING=utf-8` 环境变量，否则 Python 子进程在 PIPE 模式下会用系统编码（中文 Windows 的 cp936）导致 emoji 等 Unicode 崩溃。

### 终止进程
- **Windows 上唯一可靠终止进程树的方式：`taskkill /f /t /pid <pid>`**。实测 0.3 秒，杀父进程 + 所有子进程，零孤儿。
- `WM_CLOSE`（`taskkill /pid`，不带 `/f`）对无窗口的控制台进程**完全无效**。不要在这个上面浪费时间。
- `subprocess.Popen.terminate()` 在 Windows 上调 `TerminateProcess`（等于强杀），不会优雅退出。而且杀不掉 `shell=True` 启动的 cmd.exe 的子进程。
- 杀进程前**不要**主动 `close()` stdout pipe——让进程终止自然关闭写端，reader 线程收到 EOF 自动退出。先关 pipe 会死锁。
- **`taskkill /f /t /im <进程名>` 会杀掉系统上所有同名进程，不只是目标进程的子进程。** 对 `QQ.exe` 这类用户也在使用的通用进程名，用 `/im` 会误杀用户的个人应用。正确做法：用 `/pid <pid>` 精确杀，或依赖父进程的 `/t` 级联杀子进程（如 `taskkill /f /t /im NapCatWinBootMain.exe` 的 `/t` 已经覆盖其子进程 QQ.exe）。

### Output 读取
- reader 线程只负责读 pipe 和写 queue，**绝不碰 Popen 对象**（不 poll、不 terminate）。
- 主线程独占所有 Popen 操作。

## PyInstaller 打包

- `--onefile` 解压到临时目录 `_MEIxxxxx`。如果子进程加载了临时目录中的 DLL（如 VCRUNTIME140.dll），退出时 bootloader 无法清理 → 弹窗报错。
- **修复**：`--runtime-tmpdir "%LOCALAPPDATA%\AIRobotUI\runtime"` 使用持久目录，bootloader 不尝试删除。
- 退出前 `flush()` + `close()` 所有 log handler，释放文件句柄，然后 `os._exit(0)` 立即退出，避免 Python 清理过程与 bootloader 竞态。

## tkinter + pystray 双事件循环

- tkinter 的 `mainloop()` **必须**在主线程。`root.after()` 回调也运行在主线程。
- pystray 的 `icon.run()` **必须**在独立 daemon 线程。
- 两个线程之间的通信用 `root.after()` 投递，不要直接从 pystray 线程调 tkinter API。
- `root.destroy()` 不能从 `after()` 回调里直接调用（会损坏 tkinter 内部状态），应该用 `root.quit()` 退出 mainloop，mainloop 返回后再 `destroy()`。

## 多线程架构原则

- **线程数越少越好**。本项目的 6 线程架构（tkinter、pystray、monitor、2×reader、toggle/stop）经过重构砍到 3 线程（tkinter 主、pystray daemon、2×reader），所有 bug 消失。
- `queue.Queue` 是 reader 线程到主线程的最佳解耦方式。
- 用 `root.after()` 轮询代替独立 monitor 线程。
- 用 flag + poll 代替跨线程的回调链。

## 开发流程

- **遇到进程管理问题，先在 cmd 里手动跑 `taskkill` 测试**。写 Python 测试脚本比反复改代码打包快 10 倍。
- 单实例保护：Windows 命名 Mutex（`CreateMutexW` + `ERROR_ALREADY_EXISTS`）。
- 锁文件清理：AstrBot 的 `astrbot.lock` 需要在启动前删除，否则会拒绝启动。

## tkinter 窗口与对话框

- **`root.withdraw()` 有副作用**：隐藏主窗口后，`Toplevel` 无法映射到屏幕（`deiconify()` / `wm_deiconify()` / `focus_force()` 全部无效）。
- **正确做法**：打开对话框时临时 `root.attributes('-alpha', 0)`（透明）→ `deiconify()` → 创建 `Toplevel` → `grab_set()` → `withdraw()` → `alpha=1`。用户看不到主窗口，grab 正常工作。
- `root.quit()` 退出 mainloop，不能在 `after()` 回调里直接 `destroy()`。
- 窗口居中：`winfo_screenwidth/height` 减窗口宽高除以 2。
- 配置窗口相对父窗口居中：`root.winfo_x/y/width/height` 计算偏移。
- **`Toggle` 最佳实践**：可见时先 `deiconify/lift/focus_force` 闪到前台，再 `after(150, hide)` 隐藏，既提醒用户又可靠。

## 输出面板优化

- 进程输出高频时（如 AstrBot 启动爆发 300+ 行），每行都 `root.after()` 会导致 tkinter 事件队列积压卡顿。
- **限流方案**：reader 线程推 `queue.Queue`，主线程 100ms 轮询 drain 到内存 buffer，每 N ms 批量 `insert` 到 Text widget。默认 N=500ms（每秒 2 次），可配置。
- 退出前 flush 残留 buffer。

## tkinter 字体

- tkinter 的 `font` 参数**不支持 CSS 式多字体 fallback**。tuple `(family1, family2, size)` 会报 `expected integer`。
- 中文 Windows 用 `Microsoft YaHei`，系统字体链接自动回退到 `Segoe UI Emoji` 显示 emoji。
- 不要用 `Consolas`（无中文字形），`Segoe UI` 在某些系统上渲染异常。

## 项目目录规范

- 采用 `src/` `assets/` `tests/` 结构。
- `main.pyw` 入口在 `src/` 下，用 `sys.path.insert(0, os.path.dirname(__file__))`。
- PyInstaller entry 改为 `src/main.pyw`，`--icon assets/icon.ico`。
- `startup.py` 找 `airobotui.bat` 需 `os.path.dirname` 再上一级到项目根。

## 子进程输出清理

- NapCat 和 AstrBot 的输出包含 ANSI 转义码（颜色控制序列 `\x1b[32m` 等）。
- ANSI 码如果在 URL 解析之前未清理，会污染解析出的 WebUI URL（如 `http://localhost:6185\x1b[0m`），导致 `webbrowser.open()` 打开空页面。
- **修复**：reader 线程中用正则 `\x1b\[[0-9;]*[a-zA-Z]` 统一过滤所有 ANSI 序列，在入队和 URL 解析之前执行。

## WebUI URL 检测与菜单刷新

- WebUI URL 在后台 reader 线程中异步解析。解析成功后必须立即调用 `_emit_status()` 触发托盘菜单重建，否则用户要等到下次进程启停才能看到 "Open WebUI" 按钮。
- `_emit_status()` 触发的回调（`_refresh_icon`）会在 reader 线程执行，pystray 的 `icon.menu` setter 在 Windows 上线程安全。

## 代码质量

- 使用 Ruff 作为 formatter + linter：`uv run ruff format src/ && uv run ruff check src/`
- CI 中通过 GitHub Actions 自动检查（仅当 `.py` 文件变更时触发）。
- 不要残留未使用的 import 或变量，Ruff 会拦截。

## 崩溃恢复与外部进程接管

- 进程可能被 WebUI 或其他方式外部重启，导致旧 Popen 对象失效而新进程不在管理范围内。
- `taskkill /f /t /im <进程名>` 可以杀同名外部进程，但对 uv shim 启动的程序无效（shim 立即退出，实际 python.exe 脱离父子关系）。
- **修复**：添加 `psutil` 依赖，按 cwd 遍历找到持有锁文件的 python.exe 进程，用 `taskkill /f /t /pid` 精确杀掉。
- 自动重启需加 60 秒冷却（`time.monotonic()` 计时），避免频繁崩溃时重启风暴和通知轰炸。最多 3 次后停止。
