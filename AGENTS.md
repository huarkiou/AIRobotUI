# AIRobotUI 项目经验教训

Windows 托盘应用，管理 NapCat QQ 和 AstrBot 两个后台进程。

## 进程管理

- `Popen(cwd=...)` 不参与 exe 搜索，裸文件名需拼绝对路径或用 `.\` 前缀
- 子进程设 `PYTHONIOENCODING=utf-8`，否则中文 Windows (cp936) 下 emoji 崩溃
- **杀进程：`taskkill /f /t /pid <pid>`**，唯一可靠方式，0.3s 清全树。`WM_CLOSE` / `terminate()` 均无效
- **`taskkill /f /t /im <名>` 杀全系统同名进程**，不要对 `QQ.exe` 等通用名使用，改为 `/pid` 精确杀或依赖父进程 `/t` 级联
- reader 线程只读 pipe + 写 queue，**绝不碰 Popen 对象**；主线程独占 Popen 操作
- 输出限流：queue + `after(100ms)` 轮询 drain，500ms 批量 insert，防高频卡顿

## PyInstaller

- `--runtime-tmpdir "%LOCALAPPDATA%\AIRobotUI\runtime"` 避免 `_MEI` 临时目录 DLL 清理失败
- 退出前 flush/close 所有 log handler → `os._exit(0)`，防 bootloader 竞态

## tkinter + pystray

- `mainloop()` 必须在主线程，`icon.run()` 独立 daemon 线程，跨线程用 `root.after()` 投递
- `root.destroy()` 不可在 `after()` 回调调用；用 `root.quit()` 退出 mainloop 后再 destroy
- `withdraw()` 后 Toplevel 无法映射 → 用 `alpha=0` 透明化代替 withdraw
- 字体：中文 Windows 用 `Microsoft YaHei`，不支持 CSS fallback

## 崩溃恢复

- AstrBot (uv shim) 外部重启后脱离父子关系，需 psutil 按 cwd 找持有锁文件的 python.exe，用 `/pid` 杀
- 自动重启：60s 冷却，最多 3 次，防重启风暴

## 其他

- ANSI 码 (`\x1b[...m`) 在 URL 解析前过滤，否则污染 WebUI URL
- WebUI URL 解析后立即 `_emit_status()` 刷新托盘菜单
- 单实例：Windows 命名 Mutex；AstrBot 锁文件启动前删除
- Ruff: `uv run ruff format src/ && uv run ruff check src/`
