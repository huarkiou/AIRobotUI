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
