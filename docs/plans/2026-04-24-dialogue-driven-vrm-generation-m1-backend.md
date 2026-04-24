# 对话驱动 VRM 生成 M1 后端闭环记录

## 1. 目标

实现最小后端生成任务闭环：

- 创建 VRM 生成任务并立即返回，不阻塞请求线程等待 Blender 完成。
- 生成并落盘 `character_spec.json`。
- 调用外部 Blender 执行器导入并导出 VRM。
- 落盘任务记录、日志路径和产物路径。
- Blender 不可用时由后台任务标记失败，不影响 API 可用性。
- 支持取消运行中的任务，并向外部 Blender 子进程发送终止信号。

## 2. 实现范围

新增后端模块：

- `services/core/app/vrm_generation/models.py`
- `services/core/app/vrm_generation/repository.py`
- `services/core/app/vrm_generation/executor.py`
- `services/core/app/vrm_generation/service.py`
- `services/core/app/vrm_generation/runner.py`
- `services/core/app/vrm_generation/runtime.py`
- `services/core/app/api/vrm_generation_routes.py`

新增脚本与示例：

- `services/core/scripts/vrm_generation/roundtrip_vrm.py`
- `services/core/scripts/vrm_generation/character_spec.example.json`

新增测试：

- `services/core/tests/test_api_vrm_generation.py`

## 3. API

- `POST /vrm-generation/jobs`
  - 输入：`prompt`、可选 `input_model_path`、可选 `spec`
  - 输出：任务状态、错误信息、产物路径
- `GET /vrm-generation/jobs/{job_id}`
  - 输出：任务详情
- `GET /vrm-generation/jobs/{job_id}/artifacts`
  - 输出：`spec_path`、`output_vrm_path`、`log_path`
- `POST /vrm-generation/jobs/{job_id}/cancel`
  - 输出：任务详情，状态为 `cancelled` 或既有终态

## 4. 配置

- `VRM_GENERATION_STORAGE_PATH`：任务记录 JSON 路径。
- `VRM_GENERATION_ARTIFACT_DIR`：生成产物目录。
- `VRM_BLENDER_PATH`：Blender 可执行文件路径。

默认行为：

- 任务记录写入 `services/core/.data/vrm_generation/jobs.json`。
- 产物写入 `services/core/.data/vrm_generation/artifacts/`。
- 若 `/Applications/Blender.app/Contents/MacOS/Blender` 存在，则作为默认 Blender 路径。
- Blender 不存在时任务进入 `failed`，错误码为 `blender_unavailable`。

## 5. 当前边界

- 当前是导入现有 VRM 后按规格做最小材质色修改并导出，不是完整自动建模。
- 当前 prompt 到 spec 是确定性规则映射，不调用 LLM。
- 当前任务通过进程内单 worker 后台执行，避免请求线程被 Blender 长任务阻塞。
- 当前取消会终止外部子进程，但服务重启后无法恢复运行中任务。
- 当前默认模型仍是 spike 资产 `apps/desktop/public/avatar/xiaoyan.vrm`。

## 6. 验证结果

已执行：

```bash
cd services/core && python3 -m pytest tests/test_api_vrm_generation.py -q
```

结果：`5 passed`。

覆盖内容：

- fake Blender 成功任务会落盘产物和任务记录。
- Blender 缺失时任务进入 `failed`，错误码为 `blender_unavailable`。
- 慢速 Blender 任务创建接口会在 0.5 秒内返回。
- 运行中任务可以通过 cancel endpoint 进入 `cancelled`。
- cancel 会终止外部进程，避免取消后继续产出 `output.vrm`。

真实 Blender API 烟测：

```bash
VRM_GENERATION_STORAGE_PATH=<tmp>/jobs.json \
VRM_GENERATION_ARTIFACT_DIR=<tmp>/artifacts \
VRM_BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender \
python3 - <<'PY'
from fastapi.testclient import TestClient
from pathlib import Path
from app.main import app
client = TestClient(app)
resp = client.post('/vrm-generation/jobs', json={'prompt':'小晏，浅棕短发，蓝眼睛，白色居家裙'})
payload = resp.json()
assert resp.status_code == 200
assert payload['status'] == 'completed'
assert Path(payload['artifacts']['output_vrm_path']).is_file()
PY
```

结果：生成任务返回 `completed`，产物 `.vrm` 文件存在。

文件体积检查：

```bash
python3 tools/check_file_budgets.py
```

结果：通过；仍提示 3 个既有大文件告警，非本次新增。

## 7. 下一步（唯一）

进入 M2 前准备可编辑基础 `.blend` 模板或替换当前 spike VRM 资产，避免继续围绕临时模型扩展生成能力。
