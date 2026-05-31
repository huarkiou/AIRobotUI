# TrayForge 项目经验教训

Windows 托盘应用，通用进程管理（NapCat QQ、AstrBot、llama.cpp 等）。

## 进程管理

- ProcessManager 通用化：`_procs: dict[str, _ProcState]` 按名索引，不再硬编码 per-process 属性对
- 配置驱动：`processes[]` 数组，每个进程独立配置 name/cwd/cmd/encoding/singleton/autostart/webui_pattern/delete_before_start
- `shlex.split(cmd, posix=False)` 必须在 Windows 使用，否则反斜杠路径被当 POSIX 转义符吃掉
- `Popen(cwd=...)` 不参与 exe 搜索，裸文件名需拼绝对路径或用 `.\` 前缀；含 `..` 的相对路径（如 `..\python_embeded\python.exe`）会在 cwd 下解析
- 子进程设 `PYTHONIOENCODING=utf-8`，否则中文 Windows (cp936) 下 emoji 崩溃
- **杀进程：`taskkill /f /t /pid <pid>`**，唯一可靠方式，0.3s 清全树。`WM_CLOSE` / `terminate()` 均无效
- **`taskkill /f /t /im <名>` 杀全系统同名进程**，不要对 `QQ.exe` 等通用名使用，改为 `/pid` 精确杀或依赖父进程 `/t` 级联
- `singleton: true` → 防同进程名重复启动（`is_running` 检查）
- `cleanup_cwd: true` → 启动前杀同工作目录的所有残留进程（psutil + taskkill），用于清理僵尸进程（NapCat/AstrBot 等）
- `singleton` 和 `cleanup_cwd` 独立控制，同 cwd 下多进程（如 llama-server 不同端口）设 `cleanup_cwd: false` 避免互杀
- `delete_before_start` → 启动前删文件，被占用时按 cwd 杀占文件进程后重试
- reader 线程只读 pipe + 写 queue，**绝不碰 Popen 对象**；主线程独占 Popen 操作
- 输出限流：per-process buffer + 按 `output_refresh_ms` 间隔 `\n`.join 批量 insert，防高频卡顿

## PyInstaller

- `--runtime-tmpdir "%LOCALAPPDATA%\TrayForge\runtime"` 避免 `_MEI` 临时目录 DLL 清理失败
- 退出前 flush/close 所有 log handler → `os._exit(0)`，防 bootloader 竞态
- 构建后**必须检查** `build/TrayForge/warn-TrayForge.txt`，确认无项目自身模块出现在 missing/invalid 条目中
- `"invalid module named X"` = 模块有语法错误，PyInstaller 无法解析 → 直接排除出 exe → 运行时 `ModuleNotFoundError`
  - `--hidden-import` 对语法错误无效，必须修模块源码
  - 排查：`python -c "import X"` 确认语法正确；排除命名冲突（`find .venv -name 'X*'`）
- 构建前断言所有源模块可导入：`python -c "import src_module_name"` 逐个验证

## 多运行模式

- 三模式入口：无参→GUI，有参→CLI client，`--headless`→后台服务。新增模式不改现有控制器
- headless 模式：`queue.Queue` + `threading.Event` 替代 `root.after()` 做跨线程 marshaling
- HTTP handler 用子类继承换 marshaling 传输（`QueueHandler` 继承 `TrayForgeHTTPHandler`，只覆写 `_marshal`）
- `_marshal` 双实现易分叉：两个分支都要单独处理 `_HTTPError` 返回、超时 guard，抽象共享 helper 降低维护风险
- headless 控制器 `try/finally` 中 `server`/`pm` 可能未初始化：先设 `None`，finally 判空再操作
- headless 输出直接写进程日志文件，需同样过滤 ANSI 码
- `--windowed` exe 在 CLI/headless 模式下用 `AttachConsole(-1)` 连接父控制台，否则 stdout 不可见

## tkinter + pystray

- `mainloop()` 必须在主线程，`icon.run()` 独立 daemon 线程，跨线程用 `root.after()` 投递
- `root.destroy()` 不可在 `after()` 回调调用；用 `root.quit()` 退出 mainloop 后再 destroy
- `withdraw()` 后 Toplevel 无法映射 → 用 `alpha=0` 透明化代替 withdraw
- 字体：中文 Windows 用 `Microsoft YaHei`，不支持 CSS fallback

## 崩溃恢复

- 通用化：所有进程统一走 `poll_crashes()` 遍历 `_procs`，60s 冷却 + 最多 3 次重启
- `delete_before_start` 泛化了旧的 AstrBot 锁文件删除逻辑，不再硬编码

## CLI 控制

- 同 exe 多模式：无参数启动 GUI，带参数启动 CLI，`--headless` 启动后台服务
- CLI 通过 HTTP (`127.0.0.1:<port>`) 与运行中的实例通信
- headless 模式：ProcessManager + HTTP server，无 GUI，纯后台运行，Ctrl+C 退出
- headless 用 Queue + Event 替代 tkinter 主循环，HTTP handler 继承同一套端点
- 端口发现：实例启动时将端口写入 `cli_port.txt`，CLI 读取后连接
- CLI 命令：`list` `status <name>` `start <name>` `stop <name>` `restart <name>` `webui <name>` `reload`
- CLI 用 `argparse` 子命令，`--help` 输出用法
- `--windowed` 打包的 exe 在 CLI/headless 模式下通过 `AttachConsole(-1)` 连接父控制台输出

## 环境变量

- `TRAYFORGE_DATA_DIR` — 覆盖数据目录（`config.json`、`cli_port.txt`、日志等），测试时用于隔离生产配置

## 测试

- 127 个单元测试：cli (20)、config_ui (25)、process_mgr (22)、http_server (23)、main_window (11)、startup (10)、headless (4)、config (7)、logger (5)
- 7 个集成测试
- 全部测试：`uv run pytest tests/ -v`（134 tests）
- 集成测试需要桌面会话（tkinter 依赖 display）

## tkinter 陷阱

- **`notebook.forget(widget)` 必须传入 `notebook.add()` 时的同一个 widget，不能是子孙 widget**
  - 错误示例：`text_widget.master.master` → 得到 `tk.Frame`（depth 2），但 `notebook.add()` 传入的是 `ttk.Frame`（depth 3）
  - 传入非直属子 widget 会静默抛 `TclError`（在 `after` 回调中被 tkinter 吞掉），窗口无任何更新
  - 正确做法：用 `notebook.tabs()` + `notebook.tab(tab_id, "text")` API 按名称查找和删除 Tab，不依赖 `.master` 层级
- **Canvas 内嵌 frame 宽度不跟随**：`canvas.create_window()` 默认窗口宽度为 widget 自然宽度，不会随 canvas 拉伸
  - 解决：`canvas.bind("<Configure>", lambda e: canvas.itemconfig(window_id, width=e.width))` 让窗口宽度跟踪 canvas
  - 否则 `pack(fill=tk.X)` 在 canvas 内部的 frame 无法横向填满，内容贴左不贴右
- **按钮回调用 frame 引用而非 idx 闭包**：当列表条目可重排序时，idx 闭包会指向错误位置
  - 正确做法：所有按钮 `command=lambda f=frame: self._handler(f)`，内部 `_find_index(frame)` 查找当前位置

## 其他

- 启动错误（cwd 不存在、cmd 为空、可执行文件找不到）通过 `_system_msg()` 写入输出面板，用户可直接在窗口中看到原因，不再仅依赖日志文件
- `delete_before_start` 失败（权限不足、路径逃逸）也通过 `_system_msg()` 提示
- 配置校验：name 不能含 `/` `\`；webui_pattern 保存时试编译正则，无效则报错
- **配置自动备份**：`save_config()` 写入前先复制旧文件到 `backups/config.<timestamp>.json`，备份目录超过 10MB 时自动清理最旧文件
- ANSI 码 (`\x1b[...m`) 在 URL 解析前过滤，否则污染 WebUI URL
- WebUI URL 解析后立即 `_emit_status()` 刷新托盘菜单
- 单实例：Windows 命名 Mutex
- Windows 任务栏图标：`SetCurrentProcessExplicitAppUserModelID` + `iconbitmap(.ico)`，`iconphoto()` 只管标题栏
- MainWindow Tab 动态化：`set_processes(names)` 按进程名创建/销毁 Tab
- TrayUI 菜单动态化：遍历 `process_names()` 生成子菜单，WebUI URL 直接显示在菜单项中
- **Reload Config**：运行时从磁盘重载配置文件，无需重启应用
- 托盘 Show Window 菜单：始终显示窗口，仅手动关闭（× / 任务栏关闭）才隐藏。点击时用 `lift()` + `focus_force()` 提到前台
- Toplevel 对话框复用：托盘菜单项再次点击时不要静默忽略，应 `lift()` + `focus_force()` + `grab_set()` 将已有对话框提到前台
- Settings 动态化：可滚动进程列表 + Add/Delete/Copy/▲▼ 按钮 + cleanup_cwd checkbox
  - 进程行构建提取为 `_build_process_row()`，`_add_process` 和 `_insert_process` 复用
  - Copy/上移/下移后通过 `_repack()`（`pack_forget` + 按序 `pack`）刷新布局
  - Cmd 字段旁 `...` 按钮弹出多行编辑对话框，Save 时换行自动替换为空格
- Ruff: `uv run ruff format src/ && uv run ruff check src/`
- 架构：`AppController` 类集中管理事件循环、action 分发、输出缓冲、启停全流程；`main.pyw` 仅入口
- 类型：`trayforge_types.py` 定义 `ProcessConfig` 和 `AppConfig` TypedDict，各模块统一引用
- 后向兼容代码：确认已无旧数据依赖后再删除迁移逻辑，同时清理测试和文档引用
