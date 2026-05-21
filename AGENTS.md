# TrayForge 项目经验教训

Windows 托盘应用，通用进程管理（NapCat QQ、AstrBot、llama.cpp 等）。

## 进程管理

- ProcessManager 通用化：`_procs: dict[str, _ProcState]` 按名索引，不再硬编码 per-process 属性对
- 配置驱动：`processes[]` 数组，每个进程独立配置 name/cwd/cmd/encoding/singleton/autostart/webui_pattern/delete_before_start
- `shlex.split(cmd, posix=False)` 必须在 Windows 使用，否则反斜杠路径被当 POSIX 转义符吃掉
- `Popen(cwd=...)` 不参与 exe 搜索，裸文件名需拼绝对路径或用 `.\` 前缀
- 子进程设 `PYTHONIOENCODING=utf-8`，否则中文 Windows (cp936) 下 emoji 崩溃
- **杀进程：`taskkill /f /t /pid <pid>`**，唯一可靠方式，0.3s 清全树。`WM_CLOSE` / `terminate()` 均无效
- **`taskkill /f /t /im <名>` 杀全系统同名进程**，不要对 `QQ.exe` 等通用名使用，改为 `/pid` 精确杀或依赖父进程 `/t` 级联
- `singleton: true` → 启动前按 cwd 杀同目录进程（psutil + taskkill），替代旧的按镜像名杀
- `delete_before_start` → 启动前删文件，被占用时按 cwd 杀占文件进程后重试
- reader 线程只读 pipe + 写 queue，**绝不碰 Popen 对象**；主线程独占 Popen 操作
- 输出限流：per-process buffer + 按 `output_refresh_ms` 间隔 `\n`.join 批量 insert，防高频卡顿

## PyInstaller

- `--runtime-tmpdir "%LOCALAPPDATA%\TrayForge\runtime"` 避免 `_MEI` 临时目录 DLL 清理失败
- 退出前 flush/close 所有 log handler → `os._exit(0)`，防 bootloader 竞态

## tkinter + pystray

- `mainloop()` 必须在主线程，`icon.run()` 独立 daemon 线程，跨线程用 `root.after()` 投递
- `root.destroy()` 不可在 `after()` 回调调用；用 `root.quit()` 退出 mainloop 后再 destroy
- `withdraw()` 后 Toplevel 无法映射 → 用 `alpha=0` 透明化代替 withdraw
- 字体：中文 Windows 用 `Microsoft YaHei`，不支持 CSS fallback

## 崩溃恢复

- 通用化：所有进程统一走 `poll_crashes()` 遍历 `_procs`，60s 冷却 + 最多 3 次重启
- `delete_before_start` 泛化了旧的 AstrBot 锁文件删除逻辑，不再硬编码

## 其他

- 启动错误（cwd 不存在、cmd 为空、可执行文件找不到）通过 `_system_msg()` 写入输出面板，用户可直接在窗口中看到原因，不再仅依赖日志文件
- ANSI 码 (`\x1b[...m`) 在 URL 解析前过滤，否则污染 WebUI URL
- WebUI URL 解析后立即 `_emit_status()` 刷新托盘菜单
- 单实例：Windows 命名 Mutex
- Windows 任务栏图标：`SetCurrentProcessExplicitAppUserModelID` + `iconbitmap(.ico)`，`iconphoto()` 只管标题栏
- MainWindow Tab 动态化：`set_processes(names)` 按进程名创建/销毁 Tab
- TrayUI 菜单动态化：遍历 `process_names()` 生成子菜单，WebUI 入口按 `webui_pattern` 有无动态显示
- Settings 动态化：可滚动进程列表 + Add/Delete，不再硬编码固定进程
- Ruff: `uv run ruff format src/ && uv run ruff check src/`
