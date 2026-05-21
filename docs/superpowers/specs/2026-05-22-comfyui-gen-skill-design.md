# ComfyUI Image Generation Skill

Date: 2026-05-22  
Type: 新增 skill + TrayForge 集成配置

## 目标

让 AI agent 能够通过 CLI 控制 ComfyUI 生成图片，并提供 skill 文件指导 agent 完成此工作。

## 架构

两个交付物：
1. **Skill 文件** `D:\Apps\ai\pi\skills\comfyui-gen\SKILL.md` — 指导 agent 使用 comfy-cli
2. **TrayForge 可选的 ComfyUI 进程配置** — 方便用户管理

## Skill 文件结构

触发条件：用户提到生图、ComfyUI、workflow、generate image 等。

### 1. 前置条件
- ComfyUI 安装于 `D:\Apps\ai\ComfyUI\ComfyUI`
- `comfy-cli` 通过 `uv tool install comfy-cli` 安装
- 首次运行处理 tracking 弹窗：`comfy tracking disable`

### 2. 启动 ComfyUI（两种策略）
- **优先 TrayForge：** 若 TrayForge 运行中且有 ComfyUI 进程配置，从托盘启动
- **降级 CLI：** 若 TrayForge 不可用 → `comfy --skip-prompt launch --background -- --port 8188`，标记为 CLI 启动

### 3. 常用命令
```bash
# 运行 workflow（同步等待）
comfy --skip-prompt run --workflow <file.json> --host 127.0.0.1 --port 8188 --wait --timeout 120

# 列出模型
comfy model list

# 后台启动/停止
comfy --skip-prompt launch --background -- --port 8188
comfy stop
```

### 4. Workflow JSON 格式
- 从 ComfyUI Web UI 导出 "API Format" workflow JSON
- 关键节点：LoadCheckpoint、CLIPTextEncode、KSampler、VAEDecode、SaveImage
- 修改 prompt：找到 `"class_type": "CLIPTextEncode"` 节点的 `inputs.text` 字段

### 5. 示例场景
- **文生图：** `comfy run --workflow txt2img.json ...`
- **图生图：** workflow 需含 LoadImage 节点，指定 `inputs.image` 路径
- **批量：** 写 for 循环调用 `comfy run`

### 6. TrayForge 集成（可选）
```json
{
    "name": "ComfyUI",
    "cwd": "D:\\Apps\\ai\\ComfyUI\\ComfyUI",
    "cmd": "..\\python_embeded\\python.exe main.py --port 8188",
    "webui_pattern": "To see the GUI go to: (https?://\\S+)",
    "singleton": true,
    "cleanup_cwd": false
}
```

### 7. 故障排查
- Tracking 弹窗 → `comfy tracking disable`
- 端口占用 → 改 `--port` 参数
- Workflow 校验失败 → 检查节点名和输入类型

### 8. 清理
- 若 ComfyUI 通过 CLI 启动（非 TrayForge 管理），任务完成后询问用户是否需要 `comfy stop`
- 若 TrayForge 管理，由用户自行在托盘停止
