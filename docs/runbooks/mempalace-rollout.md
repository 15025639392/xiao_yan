# MemPalace Rollout Runbook (小晏 Core)

## 1. 目标

- 在不改用户侧交互的前提下，将 `/chat` 的记忆检索与会话历史统一切到 `MemPalace`。
- 记忆系统已统一到 `MemPalace`，`/chat` 与记忆面板共用同一底层存储。

## 2. 配置项

在 `services/core/.env.local` 中：

- `MEMPALACE_PALACE_PATH`：MemPalace 数据目录
  - 默认：`services/core/.mempalace/palace`（服务端根目录）
  - 约束：运行时仅允许 `services/core` 根目录内路径；外部绝对路径会自动回退到默认目录
- `MEMPALACE_RESULTS_LIMIT`：每次注入 prompt 的最大命中条数（建议 `3`）
- `MEMPALACE_WING`：写入 wing（默认 `wing_xiaoyan`）
- `MEMPALACE_ROOM`：写入 room（默认 `chat_exchange`）

说明：当前版本聊天链路已强制启用 MemPalace，`MEMPALACE_ENABLED` 不再作为开关。

## 3. 依赖安装

在 `services/core` 执行：

```bash
pip install -e .
```

如果需要单独装：

```bash
pip install "mempalace>=3.1.0"
```

- 当前环境状态（2026-04-13）：
  - `mempalace==3.1.0`
  - `chromadb==0.6.3`
  - `mempalace_drawers` collection 可正常打开（说明 palace 可读写）
- 建议验收命令：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
python - <<'PY'
import mempalace, chromadb
from pathlib import Path
print("mempalace", getattr(mempalace, "__version__", "unknown"))
print("chromadb", getattr(chromadb, "__version__", "unknown"))
client = chromadb.PersistentClient(path=str(Path(".mempalace/palace")))
col = client.get_collection("mempalace_drawers")
print("collection", col.name, "count", col.count())
PY
```

## 4. 初始化 MemPalace（首次）

```bash
mempalace init /path/to/seed-data
mempalace mine /path/to/seed-data --mode convos
```

说明：可以先导入历史会话导出，再让小晏在线持续镜像新对话。

## 5. 灰度步骤

1. 启动服务，确认可读写 palace。
2. 使用 10~20 条真实问答做回归：
   - 观察 `/chat` 是否 200
   - 观察回答是否出现长期记忆线索
   - 观察是否有异常日志（search/record）
3. 如异常率可接受，扩大流量；否则回滚。

## 6. 验证清单

```bash
pytest -q services/core/tests/test_mempalace_adapter.py
pytest -q services/core/tests/test_api_chat.py -k "mempalace"
pytest -q services/core/tests/test_autonomy_loop.py services/core/tests/test_prompt_builder.py
```

通过标准：全部通过，且 `/chat` 功能无回归。

## 7. 回滚方案

- 立即回滚：
  - 回滚到切换前版本（Git 回退）
  - 重启 `services/core`
- 当前版本不再支持通过环境变量切回旧聊天记忆链路。

## 8. 观测建议

- 基线指标（可通过 `GET /memory/observability` 获取）：
  - `latency.retrieval_ms.p95`：长期记忆检索 P95（阈值 120ms）
  - `latency.chat_ms.p95`：聊天链路 P95（阈值 1500ms）
  - `quality.hit_rate`：长期检索命中率（阈值不低于 40%）
  - `write.failure_rate`：记忆写入失败率（阈值不高于 1%）
- 告警样本门槛（`thresholds` 字段）：
  - `min_latency_samples_for_alert`：20
  - `min_write_samples_for_alert`：20
  - `min_quality_samples_for_alert`：20
- 告警信号（`alerts` 字段）：
  - `retrieval_p95_above_120ms`
  - `chat_p95_above_1500ms`
  - `retrieval_hit_rate_below_40pct`
  - `write_failure_rate_above_1pct`
- 观测解释：
  - 当当前数据集中没有可用跨 room 长期源（仅当前会话 room 与事件镜像 room）时，长期检索会自动跳过，对应 `quality.queries=0` 属于预期行为。
- 建议巡检命令：

```bash
curl -s http://127.0.0.1:8000/memory/observability | jq
```

## 9. 风险与处理

- 若 MemPalace/Chroma 未安装：适配器会降级，不应影响主链路。
- 当前机器检查结果（2026-04-13）：依赖已安装，不处于“未安装导致的降级”状态。
- Palace 路径不存在：search 为空，record 失败并告警。
- 数据膨胀：可通过 `MEMPALACE_RESULTS_LIMIT` 和外部归档策略控制。

## 10. 灰度前自动验收（本地）

- 目的：在进入真实流量灰度前，先用本地可重复脚本验证观测链路可用、指标结构完整。
- 脚本：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
PYTHONPATH=. python tools/mempalace/mempalace_observability_preflight.py --turns 12
```

- 产出：`docs/runbooks/evidence/mempalace-preflight-*.json`
- 说明：该脚本使用本地 TestClient + stub gateway/mempalace 进行预验收；真实灰度仍需按第 5 节执行 10~20 条真实问答并记录指标快照。

## 11. 真实流量灰度预检（带重试）

- 目的：对本地运行中的真实服务做 10~20 轮 `/chat` 调用，容忍单轮超时/502，保留完整重试轨迹并输出 observability 前后快照。
- 脚本：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
PYTHONPATH=. python tools/mempalace/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8000 --turns 12 --retries 3 --reset-first
```

- 产出：`docs/runbooks/evidence/mempalace-live-preflight-*.json`
- 最近证据（2026-04-13）：
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-180042.json`
  - 结果：12/12 成功（reset-first）
  - 告警：none
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-173408.json`
  - 结果：10/10 成功（重试后无失败）
  - 告警：none
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-171217.json`
  - 结果：12/12 最终成功（含自动重试）
  - 告警：`retrieval_p95_above_120ms`、`chat_p95_above_1500ms`、`retrieval_hit_rate_below_40pct`

## 12. 24h 灰度观察（持续采样）

- 目的：在 10% 灰度窗口持续采集 `/memory/observability`，形成上线门禁证据链。
- 脚本：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
PYTHONPATH=. python tools/mempalace/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --duration-minutes 1440 --interval-seconds 300 --reset-first
```

- 启动方式（后台）：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
nohup env PYTHONPATH=. python tools/mempalace/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --duration-minutes 1440 --interval-seconds 300 --reset-first > /tmp/mempalace-gray-watch.log 2>&1 &
```

- 产出：`docs/runbooks/evidence/mempalace-gray-watch-*.json`
- 首次基线证据（2026-04-13）：
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-gray-watch-20260412-180200.json`
  - 结果：`alerts_union=[]`（reset-first）
  - 说明：该证据用于验证观察链路与重置流程可用，不代表 24h 最终样本充足性
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-gray-watch-20260412-174025.json`
  - 结果：`alerts_union=[]`
  - 说明：当前样本充足性为 false（流量样本未达到 20 条门槛），需继续观察窗口。

## 13. 知识管理面板 MVP 约定（2026-04-13）

- 目标：在不新增独立“知识库后台”的前提下，先复用现有记忆面板完成结构化知识管理闭环。
- 前端入口：`#/memory` 页面新增模式切换：
  - `全部记忆`：沿用原有记忆视图。
  - `结构化知识`：限定展示结构化知识命名空间。
- API 约定（关键）：
  - 结构化模式下，时间线与搜索统一走 `/memory/timeline`，并带 `namespace=knowledge`。
  - 搜索词通过 `q` 参数透传（仍保留 `namespace=knowledge` 作用域）。
- 所有权约定：
  - 结构化知识由服务端治理与写入（接口服务端为 owner）。
  - 默认存储路径在服务端根目录：`services/core/.mempalace/palace`，不使用用户 home 目录 `~/.mempalace/palace`。
- 后续演进：
  - 若需要独立管理后台，再在该 MVP 基础上追加“结构化知识专用面板”，避免重复建设。
