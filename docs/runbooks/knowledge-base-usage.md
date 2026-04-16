# 知识库详细使用手册（小晏 Core）

更新时间：2026-04-13

## 1. 文档目标

这份文档用于统一回答三个问题：

1. 知识库内容是如何产出的（自动抽取 + 手动维护）。
2. 知识库数据存在哪里、谁是 owner、如何保证路径受控。
3. 日常如何查询、管理、排障与验证。

## 2. 总体架构（先看这个）

- 统一存储：知识与记忆共用 MemPalace/Chroma。
- 服务端 owner：结构化知识由 `services/core` 服务端治理和写入。
- 前端入口：`#/memory` 页面。
  - `全部记忆`：看全量。
  - `结构化知识`：固定查询 `namespace=knowledge`。

一句话理解：前端是管理入口，真正的知识产出、落库、约束都在服务端完成。

## 3. 存储路径与受控规则

### 3.1 默认路径

- 默认存储路径：`services/core/.mempalace/palace`

### 3.2 路径约束（重要）

运行时仅允许落在 `services/core` 根目录内。  
即使错误配置为外部路径（如 `~/.mempalace/palace`、`/tmp/xxx`、主控目录路径），也会自动回退到默认路径：

- `services/core/.mempalace/palace`

### 3.3 快速检查当前生效路径

```bash
curl -sS http://127.0.0.1:8000/config/data-environment | jq '.mempalace_palace_path, .testing_mode, .mempalace_room'
```

预期：

- `mempalace_palace_path` 指向 `/.../services/core/.mempalace/palace`
- `testing_mode=false`（除非你主动开测试数据模式）

## 4. 知识内容如何产出

知识内容有两条主链路。

### 4.1 自动产出（对话后抽取）

触发入口：`POST /chat` 与 `POST /chat/resume`

流程：

1. 用户消息进入聊天链路。
2. 模型生成回复后，服务端先镜像 user/assistant 对话到记忆事件。
3. 若开启 `CHAT_KNOWLEDGE_EXTRACTION_ENABLED=true`：
   - `MemoryExtractor` 从这一轮对话中抽取结构化事件；
   - 典型类型包括：偏好、习惯、边界、事实、承诺、学习点；
   - 抽取结果会做去重、标签归一、来源元数据补齐；
   - 最终写入知识命名空间（`namespace=knowledge`）。

### 4.2 手动产出（面板/API 新建）

触发入口：

- 前端记忆面板点“新建”
- 或 `POST /memory`

手动创建 `fact/semantic/episodic/emotional` 这类条目时，会进入知识命名空间逻辑；可用于纠偏、补录、运营维护。

### 4.3 从入库到聊天注入（发布策略）

结构化知识写入后，不会无差别进入聊天上下文，而是走“审核 + 排序”策略：

1. 过滤阶段：仅 `namespace=knowledge` 且 `review_status=approved` 的条目可参与注入。
2. 候选集：按最近窗口拉取候选（默认拉取 `max(max_hits*5, 20)` 条）。
3. 排序阶段：按“相关性 + 新鲜度”混合分排序，再截断到 `max_hits`。

当前打分规则（2026-04-13）：

- 相关性分（0~1）：基于当前用户发言与知识内容/标签/类型/来源的 token 重叠度，命中整句有额外 bonus。
- 新鲜度分（0~1）：按时间衰减计算（半衰期 14 天）。
- 混合分：当用户发言可分词时，`0.75 * 相关性 + 0.25 * 新鲜度`；否则仅按新鲜度排序。

`max_hits` 由聊天上下文预算推导（`CHAT_CONTEXT_LIMIT * LONG_TERM_CONTEXT_WEIGHT`，最小 1）。

## 5. 开关与配置

配置文件：`services/core/.env.local`

推荐配置：

```dotenv
MEMPALACE_PALACE_PATH=.mempalace/palace
MEMPALACE_RESULTS_LIMIT=3
MEMPALACE_WING=wing_xiaoyan
MEMPALACE_ROOM=chat_exchange
CHAT_KNOWLEDGE_EXTRACTION_ENABLED=true
```

说明：

- `MEMPALACE_PALACE_PATH` 建议始终使用相对路径 `.mempalace/palace`。
- `MEMPALACE_RESULTS_LIMIT` 控制注入 prompt 的长期记忆命中条数。
- `CHAT_KNOWLEDGE_EXTRACTION_ENABLED` 控制是否启用对话后结构化抽取。

## 6. API 使用手册

### 6.0 知识专项 API（新增）

当你需要“审核态治理”时，优先使用 `/knowledge/*`：

- `GET /knowledge/items`：知识列表（支持 `review_status/status/q`）
- `GET /knowledge/summary`：知识汇总（按审核状态、类型统计）
- `POST /knowledge/items`：创建人工知识（默认 `approved`）
- `POST /knowledge/items/{id}/review`：审核（`approve/reject/pend`）
- `POST /knowledge/items/review-batch`：批量审核

`GET /knowledge/items` 现支持稳定分页与排序控制（推荐）：

- `sort_by`：`created_at | reviewed_at`（默认 `created_at`）
- `sort_order`：`desc | asc`（默认 `desc`）
- `cursor`：游标翻页令牌（与 `sort_by/sort_order` 绑定）
- `offset`：保留兼容参数；与 `cursor` 不能同时使用

返回字段新增：

- `next_cursor`：下一页游标；为空表示没有更多结果
- `next_offset`：offset 模式下的下一页偏移量（cursor 模式下为空）

示例：

```bash
# 列出待审核知识
curl -sS "http://127.0.0.1:8000/knowledge/items?review_status=pending_review&limit=20" | jq

# 稳定分页（推荐：cursor + sort）
FIRST_PAGE=$(curl -sS "http://127.0.0.1:8000/knowledge/items?limit=20&sort_by=created_at&sort_order=desc")
echo "$FIRST_PAGE" | jq '.items[].id, .next_cursor'
NEXT_CURSOR=$(echo "$FIRST_PAGE" | jq -r '.next_cursor')
curl -sS "http://127.0.0.1:8000/knowledge/items?limit=20&sort_by=created_at&sort_order=desc&cursor=${NEXT_CURSOR}" | jq

# 审核通过
curl -sS -X POST "http://127.0.0.1:8000/knowledge/items/<id>/review" \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","reviewer":"knowledge-owner","review_note":"信息准确，可发布"}' | jq

# 批量驳回（reject 时 review_note 必填）
curl -sS -X POST "http://127.0.0.1:8000/knowledge/items/review-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_ids":["mem_a","mem_b"],
    "decision":"reject",
    "reviewer":"knowledge-owner",
    "review_note":"证据不足，需补来源"
  }' | jq
```

### 6.1 查询知识（最常用）

```bash
curl -sS "http://127.0.0.1:8000/memory/timeline?limit=20&namespace=knowledge" | jq
```

可用筛选参数：

- `limit`：返回条数
- `status`：`active | deleted | all`
- `kind`：`fact | episodic | semantic | emotional | chat_raw`
- `namespace`：如 `knowledge`
- `visibility`：`internal | user`
- `q`：关键词搜索

### 6.2 新建知识

```bash
curl -sS -X POST "http://127.0.0.1:8000/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "kind":"fact",
    "content":"用户偏好晨间同步，每天 09:30 前完成",
    "role":"user"
  }' | jq
```

### 6.3 更新知识

```bash
curl -sS -X PUT "http://127.0.0.1:8000/memory/<memory_id>" \
  -H "Content-Type: application/json" \
  -d '{"content":"用户偏好晨间同步，工作日 09:30 前完成"}' | jq
```

### 6.4 软删除与恢复

```bash
# 软删除
curl -sS -X DELETE "http://127.0.0.1:8000/memory/<memory_id>" | jq

# 恢复
curl -sS -X POST "http://127.0.0.1:8000/memory/<memory_id>/restore" | jq
```

### 6.5 观测指标

```bash
curl -sS "http://127.0.0.1:8000/memory/observability" | jq
```

重点字段：

- `latency.retrieval_ms`：检索延迟
- `latency.chat_ms`：聊天延迟
- `quality.hit_rate`：检索命中率
- `write.failure_rate`：写入失败率
- `alerts`：告警信号

## 7. 前端管理面板使用

入口：桌面端 `#/memory`

### 7.1 全部记忆模式

- 用于查看聊天镜像 + 结构化事件全景。
- 适合排查“为什么模型回答成这样”。

### 7.2 结构化知识模式

- 默认查询 `namespace=knowledge`。
- 搜索也保持在 `knowledge` 作用域（不会串到 chat 原始镜像）。
- 适合运营维护、知识巡检与修正。

### 7.3 知识审核模式（分页）

- `知识审核` 面板分页默认策略：
  - `待审核/全部`：`created_at desc`
  - `已通过/已驳回`：`reviewed_at desc`
- 滚动接近列表底部时会自动使用后端返回的 `next_cursor` 继续翻页并追加结果。
- 自动翻页失败时，面板会展示“重试加载更多”按钮作为兜底入口。
- 兜底重试采用指数退避锁定（1s -> 2s -> 4s ...，最大 16s），锁定结束后可再次手动重试。
- 前后端已约定：优先使用 cursor 分页；`offset` 仅保留兼容。

## 8. 标准操作流程（推荐）

### 8.1 首次启用

1. 确认依赖：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
pip install -e .
```

2. 检查路径生效：

```bash
curl -sS http://127.0.0.1:8000/config/data-environment | jq '.mempalace_palace_path'
```

3. 打开抽取开关：`CHAT_KNOWLEDGE_EXTRACTION_ENABLED=true`
4. 重启 `services/core`
5. 发 3~5 轮真实对话，确认 `/memory/timeline?namespace=knowledge` 有新增

### 8.2 日常运营

1. 每天巡检：
   - `GET /memory/observability`
   - `GET /memory/timeline?namespace=knowledge&limit=50`
2. 每周清理：
   - 删除低价值/重复条目（软删除）
   - 恢复误删条目

### 8.3 版本发布前

建议至少跑：

```bash
cd /Users/ldy/Desktop/map/ai/services/core
pytest -q tests/test_config_paths.py
pytest -q tests/test_mempalace_adapter.py
pytest -q tests/test_api_chat.py -k mempalace
pytest -q tests/test_api_memory.py
```

## 9. 常见问题排障

### Q1：为什么看不到知识新增？

按顺序检查：

1. `CHAT_KNOWLEDGE_EXTRACTION_ENABLED` 是否开启。
2. 抽取内容是否匹配规则（偏好/事实/承诺等表达越明确越容易命中）。
3. 是否在 `namespace=knowledge` 视图下查询。
4. `GET /memory/observability` 是否出现写入失败告警。
5. 新增专项流程下，自动抽取内容默认会进入 `pending_review`，需要在 `/knowledge/items` 中审核后进入稳定发布态。
6. 审核为 `reject` 时必须填写 `review_note`，否则接口会返回 400。

### Q2：为什么感觉写到了“主控目录”？

先看生效路径：

```bash
curl -sS http://127.0.0.1:8000/config/data-environment | jq '.mempalace_palace_path'
```

若不是 `services/core/.mempalace/palace`：

1. 重启 `services/core`（确保加载新配置与路径约束逻辑）。
2. 检查是否开启了测试数据模式（`testing_mode=true` 会切到 testing 数据根）。

### Q3：历史数据在 `~/.mempalace/palace`，怎么迁移？

无损复制：

```bash
cd /Users/ldy/Desktop/map/ai
mkdir -p services/core/.mempalace/palace
rsync -a ~/.mempalace/palace/ services/core/.mempalace/palace/
```

迁移后重启服务，再用 `/memory/timeline?namespace=knowledge` 验证。

### Q4：为什么 `apps/desktop` 本地请求会超时、CPU 突然拉高？

高概率是后端处在重载模式（`--reload`）叠加知识库读写，导致 websocket 首次快照阻塞。

建议按以下顺序处理：

1. 用默认启动脚本（关闭 reload）：

```bash
cd /Users/ldy/Desktop/map/ai
./services/core/scripts/start_dev_server.sh
```

2. 确认服务健康与实时通道：

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/state >/dev/null
```

3. 仅在需要时开启热重载：

```bash
ENABLE_RELOAD=1 ./services/core/scripts/start_dev_server.sh
```

说明：已在服务端做了快照缓存与查询减载优化，默认模式下本地 `health/state/ws` 应保持毫秒级到亚秒级响应。

## 10. 数据治理建议

### 10.1 内容规范

- 一条知识只表达一个稳定事实/偏好。
- 避免“瞬时情绪”长期占位。
- `content` 尽量可验证、可复用、可行动。

### 10.2 标签策略

- 使用语义清晰标签：`preference`, `boundary`, `commitment`, `profile`
- 避免重复近义标签泛滥（会降低检索质量）。

### 10.3 生命周期

- 不确定先软删除，不立即硬删。
- 变更类知识更新原条目，不新建重复条目。

## 11. 安全与权限

- 结构化知识属于服务端资产，不依赖用户 home 目录持久化。
- 路径受控规则用于防止数据漂移到非预期目录。
- 若启用备份/导入，请保留审计记录（时间、操作者、源路径）。

## 12. 相关文档

- MemPalace 灰度与观测：`docs/runbooks/mempalace-rollout.md`
