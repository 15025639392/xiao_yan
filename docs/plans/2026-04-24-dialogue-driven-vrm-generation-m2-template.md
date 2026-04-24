# 对话驱动 VRM 生成 M2 模板准备记录

## 1. 目标

准备一个可被 Blender 打开和编辑的基础 `.blend` 模板，作为后续参数化生成的模板入口。

## 2. 本轮产物

源码脚本：

- `services/core/scripts/vrm_generation/prepare_blend_template.py`
- `services/core/scripts/vrm_generation/export_blend_vrm.py`

本地产物：

- `services/core/.data/vrm_generation/templates/xiaoyan_base.blend`

说明：

- `.blend` 模板位于 `.data/` 下，受 `.gitignore` 忽略，不进入源码仓库。
- 当前模板由 `apps/desktop/public/avatar/xiaoyan.vrm` 导入生成，仍属于 spike 模板，不是最终小晏正式模型。
- 模板大小约 2.0M，可用 Blender 4.5.0 打开编辑。

## 3. 已验证命令

生成模板：

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/prepare_blend_template.py \
  -- \
  --input apps/desktop/public/avatar/xiaoyan.vrm \
  --output services/core/.data/vrm_generation/templates/xiaoyan_base.blend
```

从模板导出 VRM：

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background services/core/.data/vrm_generation/templates/xiaoyan_base.blend \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/export_blend_vrm.py \
  -- \
  --spec services/core/scripts/vrm_generation/character_spec.example.json \
  --output /tmp/xiaoyan-vrm-tools/xiaoyan-from-template.vrm
```

## 4. 验证结果

- 模板生成成功：`services/core/.data/vrm_generation/templates/xiaoyan_base.blend`
- 模板导出成功：`/tmp/xiaoyan-vrm-tools/xiaoyan-from-template.vrm`
- 导出文件大小：227K
- 导出 VRM 解析结果：
  - `extensionsUsed` 包含 `VRM`
  - `hasVRM0` 为 `true`
  - `nodeCount` 为 73
  - `meshCount` 为 1
  - `skinCount` 为 1

## 5. 当前边界

- 当前模板只是从临时 VRM 反向生成的 `.blend`，可编辑性有限。
- 当前导出脚本只应用最小材质颜色变更，不做发型、衣服、表情或骨骼编辑。
- 当前后端默认仍可使用 VRM 输入路径；下一步可以增加 `VRM_GENERATION_TEMPLATE_PATH`，让后端直接从 `.blend` 模板导出。

## 6. 后端接入结果

已新增配置项：

- `VRM_GENERATION_TEMPLATE_PATH`：可选 `.blend` 模板路径。

行为：

- 配置存在且文件可读时，后端优先从 `.blend` 模板导出 VRM。
- 未配置模板时，后端保留旧的 VRM 输入模型 roundtrip 路径。
- 模板导出仍走后台 worker，支持 cancel 终止外部进程。

已验证：

```bash
VRM_GENERATION_STORAGE_PATH=<tmp>/jobs.json \
VRM_GENERATION_ARTIFACT_DIR=<tmp>/artifacts \
VRM_BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender \
VRM_GENERATION_TEMPLATE_PATH=/Users/ldy/Desktop/map/ai/services/core/.data/vrm_generation/templates/xiaoyan_base.blend \
python3 - <<'PY'
from fastapi.testclient import TestClient
from pathlib import Path
import time
from app.main import app
client = TestClient(app)
resp = client.post('/vrm-generation/jobs', json={'prompt':'小晏，浅棕短发，蓝眼睛，白色居家裙'})
job_id = resp.json()['job_id']
deadline = time.monotonic() + 10
while time.monotonic() < deadline:
    payload = client.get(f'/vrm-generation/jobs/{job_id}').json()
    if payload['status'] in {'completed', 'failed', 'cancelled'}:
        assert payload['status'] == 'completed'
        assert Path(payload['artifacts']['output_vrm_path']).is_file()
        break
    time.sleep(0.1)
PY
```

结果：任务 `completed`，产物 `.vrm` 存在。

## 7. 下一步（唯一）

接入桌面端最小生成页面，允许输入 prompt、创建任务、轮询状态并展示产物路径。
