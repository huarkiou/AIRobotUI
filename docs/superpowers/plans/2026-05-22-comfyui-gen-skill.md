# ComfyUI Generation Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a skill file to guide the AI agent in controlling ComfyUI image generation via comfy-cli, plus add optional TrayForge process config.

**Architecture:** Two independent deliverables: the skill file (always needed), and the TrayForge config (optional, for process management).

**Tech Stack:** comfy-cli, Python (for TrayForge config), uv

---

### Task 1: Create skill file at D:\Apps\ai\pi\skills\comfyui-gen\SKILL.md

**Files:**
- Create: `D:\Apps\ai\pi\skills\comfyui-gen\SKILL.md`

- [ ] **Step 1: Create the skill file**

```markdown
---
name: comfyui-gen
description: Use when the user wants to generate images via ComfyUI. Triggers: "生图", "生成图片", "ComfyUI", "workflow", "gen image", "txt2img", "img2img".
---

# ComfyUI Image Generation

Use `comfy-cli` to submit workflow-based prompts to a running ComfyUI server.

## Prerequisites

- ComfyUI installed at `D:\Apps\ai\ComfyUI\ComfyUI`
- Install comfy-cli: `uv tool install comfy-cli`
- Disable tracking popup (first run only):
  ```bash
  comfy tracking disable
  ```
  If this fails, run `comfy` once and answer `N` to the tracking prompt.

## Launch ComfyUI

Two strategies — prefer TrayForge when available.

**Option A: TrayForge (recommended)**

If TrayForge is running, start ComfyUI from its tray menu. The process is managed with crash recovery and output logging.

**Option B: CLI fallback**

If TrayForge is not available:
```bash
comfy --skip-prompt launch --background -- --port 8188
```

This starts ComfyUI as a background daemon. **Remember that this was started via CLI** — you'll need to clean it up later.

## Core Commands

### Run a workflow (synchronous — waits for completion)

```bash
comfy --skip-prompt run \
  --workflow <path-to-workflow.json> \
  --host 127.0.0.1 \
  --port 8188 \
  --wait \
  --timeout 120
```

- `--wait`: Blocks until generation completes
- `--timeout`: Fails after N seconds if not complete (adjust for complex workflows)
- Output images land in ComfyUI's `output/` directory

### List available models

```bash
comfy model list
```

### Stop background ComfyUI

```bash
comfy stop
```

## Workflow JSON Format

Workflow files are exported from ComfyUI's Web UI: **Workflow → Export (API Format)**.

### Key Node Types

| Node | Class Type | What it does |
|---|---|---|
| Checkpoint loader | `CheckpointLoaderSimple` | Loads the Stable Diffusion model |
| Positive prompt | `CLIPTextEncode` | Encodes positive prompt text |
| Negative prompt | `CLIPTextEncode` | Encodes negative prompt text |
| Empty latent | `EmptyLatentImage` | Sets resolution and batch size |
| Sampler | `KSampler` | Runs the diffusion sampling |
| VAE decode | `VAEDecode` | Converts latent to image |
| Save image | `SaveImage` | Writes output to disk |
| Load image | `LoadImage` | Loads input for img2img |

### Modifying a Workflow

To change prompts **without the Web UI**, edit the workflow JSON directly:

1. Find nodes with `"class_type": "CLIPTextEncode"`  
2. Check the `_meta.title` to distinguish positive vs negative prompt
3. Update `"inputs": {"text": "your new prompt", "clip": [...]}`

Example diff:
```json
// Before
{"inputs": {"text": "a cat", "clip": ["4", 1]}}

// After  
{"inputs": {"text": "a dog in space", "clip": ["4", 1]}}
```

## Examples

### Text-to-Image

```bash
# Use a pre-saved txt2img workflow
comfy --skip-prompt run --workflow workflows/txt2img.json --host 127.0.0.1 --port 8188 --wait
```

If you need to change the prompt, edit the workflow JSON first (see above), then run.

### Image-to-Image

Requires a workflow with a `LoadImage` node. The `LoadImage` node's `image` input expects a filename (ComfyUI resolves it from its `input/` directory). Copy your input image there first:

```bash
cp source.png D:/Apps/ai/ComfyUI/ComfyUI/input/
comfy --skip-prompt run --workflow workflows/img2img.json --host 127.0.0.1 --port 8188 --wait
```

### Batch Generation

```bash
for i in $(seq 1 10); do
  comfy --skip-prompt run --workflow workflow.json --host 127.0.0.1 --port 8188 --wait
done
```

## TrayForge Integration (Optional)

Add this process config to manage ComfyUI through TrayForge:

```json
{
    "name": "ComfyUI",
    "cwd": "D:\\Apps\\ai\\ComfyUI\\ComfyUI",
    "cmd": "..\\python_embeded\\python.exe main.py --port 8188",
    "encoding": "utf-8",
    "singleton": true,
    "autostart": false,
    "cleanup_cwd": false,
    "webui_pattern": "To see the GUI go to: (https?:\\/\\/\\S+)",
    "delete_before_start": []
}
```

## Cleanup

**If you started ComfyUI via CLI (Option B above):** After the task is complete, ask the user:

> "ComfyUI was started via CLI. Would you like me to stop it (`comfy stop`)?"

If they say yes:
```bash
comfy stop
```

**If ComfyUI is managed by TrayForge:** Do not stop it — the user controls it from the tray menu.

## Troubleshooting

| Problem | Solution |
|---|---|
| Tracking popup blocks `comfy` command | `comfy tracking disable` or answer `N` once |
| Port 8188 already in use | Use `--port 8189` in both launch and run commands |
| Workflow validation error | Check node names match installed custom nodes; export fresh API format from Web UI |
| `comfy` not found | `uv tool install comfy-cli` |
| Timeout on large images | Increase `--timeout` (e.g. 300 for high-res) |
```

- [ ] **Step 2: Verify**

- Skill file exists at `D:\Apps\ai\pi\skills\comfyui-gen\SKILL.md`
- All code blocks are syntactically valid

---

### Task 2: Add ComfyUI to TrayForge user config

**Files:**
- Modify: `%LOCALAPPDATA%\TrayForge\config.json`

- [ ] **Step 1: Add ComfyUI process config**

```bash
uv run python -c "
import json, os
path = os.path.join(os.environ['LOCALAPPDATA'], 'TrayForge', 'config.json')
with open(path) as f:
    config = json.load(f)

config['processes'].append({
    'name': 'ComfyUI',
    'cwd': r'D:\Apps\ai\ComfyUI\ComfyUI',
    'cmd': r'..\python_embeded\python.exe main.py --port 8188',
    'encoding': 'utf-8',
    'singleton': True,
    'autostart': False,
    'cleanup_cwd': False,
    'webui_pattern': r'To see the GUI go to: (https?://\\S+)',
    'delete_before_start': []
})

with open(path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('Added ComfyUI to config')
for p in config['processes']:
    print(f'  {p[\"name\"]}')
"
```

- [ ] **Step 2: Verify config is valid**

```bash
uv run python -c "
import json, os
path = os.path.join(os.environ['LOCALAPPDATA'], 'TrayForge', 'config.json')
with open(path) as f:
    config = json.load(f)
print('Processes:', len(config['processes']))
for p in config['processes']:
    print(f'  {p[\"name\"]}: cwd={p[\"cwd\"]}, cleanup_cwd={p[\"cleanup_cwd\"]}')
"
```

Expected: 6 processes listed, ComfyUI has `cleanup_cwd: false`.
