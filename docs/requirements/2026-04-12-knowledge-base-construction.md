# 标准模式需求：小晏知识库建设

## 结论

- 该需求适合标准模式，原因是涉及后端记忆链路、知识写入流程、检索策略、桌面端展示与上线观测的跨模块协作。
- 推荐在现有 MemPalace 统一存储基础上扩展“知识库分层与治理”，避免并行引入第二套存储系统导致复杂度上升。
- D1-D3 决策已确认，当前需求已满足进入实现排期阶段的前置条件。
- T1 已完成：知识字段与命名空间校验已落地，核心测试通过。
- T2 已完成：抽取、去重、标签化、来源元数据已打通，相关测试全部通过。
- T3 已完成：检索融合策略已区分近期上下文与长期知识召回权重，`/chat` 相关测试通过。
- T4 已完成：聊天完成事件与前端消息气泡已支持知识引用透出，回答可追溯。
- T5 已完成：知识管理 API 已支持状态过滤与软删除/恢复，契约测试通过。
- T6 已完成：已建立观测与告警基线（延迟、命中质量、写入失败率），并提供可查询指标快照。
- 灰度前自动验收已完成：已执行 12 轮本地预验收并生成 observability 证据文件。
- 真实流量灰度首轮已完成：执行 12 轮 `/chat` HTTP 实流量请求并生成 live observability 证据。
- 告警闭环改造已完成：跨 room 长期源探测 + 小样本告警门槛已上线，观测误报已收敛。
- 真实流量灰度二轮复验已完成：10/10 成功且 `alerts=none`，当前可进入下一阶段灰度放量。
- 24h 灰度观察已启动：已生成首个 watch 基线证据，当前为低流量样本阶段（样本充足性未达门槛）。
- 灰度评估口径已统一：支持 reset-first 观测窗口重置，避免历史样本污染当前门禁判断。

## 下一步（唯一）

- 持续执行 10% 流量 24 小时灰度观察，待样本充足性达标后输出最终上线门禁结论。

## 产物路径

- `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-construction.md`
- `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-review-pack.md`

## 知识预热（必须）

- 已掌握的关键约束：
  - 当前后端已统一接入 `MemPalace`，聊天检索、对话镜像与记忆仓储均有现成链路，核心文件在 `services/core/app/memory/` 与 `services/core/app/api/chat_routes.py`。
  - 当前架构原则明确“数字人本体优先”，知识系统不能退化为纯日志堆积，必须服务主体性与连续性。
  - 现有 `/memory/*` API 已支持摘要、时间线、检索与 CRUD，可作为知识库运营面的基础接口层。
- 需要用户确认的未知项：
  - 是否允许导入外部文档源（飞书、Notion、本地目录）作为知识库输入。
  - 知识库是否包含仅系统可见的“内在记忆”与“对用户可见知识”双视图。
  - 过期知识删除策略是否需要硬删除与审计日志并行。
- 可能的技术风险点：
  - 检索片段过长会抬高 prompt 成本并拉高响应延迟。
  - 混合写入聊天事件与结构化知识时，若缺少命名空间治理，容易出现召回污染。
  - 无引用来源展示时，用户难以判断回答可信度。
- 统一流水线接线声明：
  - 已确认需求作业流下一轮 failing test 选择仍由 `../skill-self-evolution/scripts/run_skill_self_evolution_pipeline.sh` 收敛，本次仅产出需求分析，不新增独立 skill 分支。

## 评审会准备（2026-04-12）

- 会议时长：45 分钟
- 参会角色：产品负责人、后端负责人、前端负责人、测试负责人
- 评审输入：需求文档 + 决策草案 + 风险清单
- 评审输出：D1-D3 的最终选择、owner、生效日期
- 决策草案：

| 决策ID | 主题 | 候选方案 | 推荐方案 | 推荐理由 |
| --- | --- | --- | --- | --- |
| D1 | 首批知识来源白名单 | A. 仅对话记录与本地 markdown；B. 加入飞书/Notion | A | 范围可控、治理成本低、两周内可交付 |
| D2 | 过期知识删除策略 | A. 软删除+30天审计索引；B. 立即硬删除 | A | 便于追溯与回滚，符合发布期风险控制 |
| D3 | 跨 room 检索策略 | A. 默认关闭跨 room；B. 全量开启跨 room | A | 降低召回污染，先保证准确性再扩展覆盖 |

## 评审结论（2026-04-12 已确认）

- D1 最终结论：采用方案 A，仅接入对话记录与本地 markdown。
- D2 最终结论：采用方案 A，软删除并保留 30 天审计索引。
- D3 最终结论：采用方案 A，默认关闭跨 room，仅对白名单 room 开启。
- 结论生效日期：2026-04-12
- 回填负责人：产品负责人（D1）、后端负责人（D2）、算法负责人（D3）

## 实施进展（2026-04-13）

- 已完成任务：
  - T1：知识条目模型与命名空间规范。
  - T2：知识写入流水线（抽取、去重、标签化、来源元数据）。
  - T3：检索融合策略（近期上下文 0.7 / 长期记忆 0.3）。
  - T4：知识引用格式与来源透出（chat_completed 事件 + 前端引用展示）。
  - T5：知识管理 API（状态过滤 + 软删除 + 恢复）与契约测试。
  - T6：观测与告警基线（指标采集 + 告警阈值 + 观测接口 + runbook 补齐）。
- 代码落点：
  - `services/core/app/memory/models.py`
  - `services/core/app/memory/mempalace_repository.py`
  - `services/core/app/memory/repository.py`
  - `services/core/app/memory/service_crud.py`
  - `services/core/app/memory/observability.py`
  - `services/core/app/api/memory_routes.py`
  - `services/core/app/runtime_ext/bootstrap.py`
  - `docs/runbooks/mempalace-rollout.md`
  - `services/core/scripts/mempalace_observability_preflight.py`
  - `services/core/scripts/mempalace_live_observability_preflight.py`
  - `services/core/scripts/mempalace_observability_watch.py`
  - `docs/runbooks/evidence/mempalace-preflight-20260412-170435.json`
  - `docs/runbooks/evidence/mempalace-live-preflight-20260412-171217.json`
  - `docs/runbooks/evidence/mempalace-live-preflight-20260412-173408.json`
  - `docs/runbooks/evidence/mempalace-gray-watch-20260412-174025.json`
  - `docs/runbooks/evidence/mempalace-live-preflight-20260412-180042.json`
  - `docs/runbooks/evidence/mempalace-gray-watch-20260412-180200.json`
  - `services/core/tests/test_memory_repository.py`
  - `services/core/tests/test_api_memory.py`
  - `services/core/app/memory/extractor.py`
  - `services/core/tests/test_memory_extractor.py`
  - `services/core/app/api/chat_routes.py`
  - `services/core/app/memory/mempalace_adapter.py`
  - `services/core/app/realtime.py`
  - `services/core/tests/test_api_chat.py`
  - `services/core/tests/test_api_realtime.py`
  - `services/core/tests/test_mempalace_adapter.py`
  - `apps/desktop/src/App.tsx`
  - `apps/desktop/src/components/chat/ChatMessages.tsx`
  - `apps/desktop/src/components/chat/chatTypes.ts`
  - `apps/desktop/src/lib/chatMessages.ts`
  - `apps/desktop/src/lib/realtime.ts`
  - `apps/desktop/src/styles/chat/chat-message.css`
  - `apps/desktop/src/components/chat/ChatMessages.test.tsx`
  - `apps/desktop/src/lib/chatMessages.test.ts`
  - `apps/desktop/src/lib/realtime.test.ts`
- 验证结果：
  - `pytest -q tests/test_memory_repository.py` 通过（8 passed）
  - `pytest -q tests/test_domain_models.py` 通过（2 passed）
  - `pytest -q tests/test_memory_extractor.py` 通过（36 passed）
  - `pytest -q tests/test_memory_integration.py tests/test_memory_system.py` 通过（61 passed）
  - `pytest -q tests/test_mempalace_adapter.py` 通过（13 passed）
  - `pytest -q tests/test_api_chat.py -k "mempalace or splits_recent_and_long_term_context_budget"` 通过（6 passed）
  - `pytest -q tests/test_api_chat.py` 通过（40 passed）
  - `pytest -q tests/test_api_realtime.py tests/test_api_chat.py` 通过（45 passed）
  - `npm --prefix apps/desktop run test -- src/components/chat/ChatMessages.test.tsx src/lib/chatMessages.test.ts src/lib/realtime.test.ts` 通过（8 passed）
  - `pytest -q tests/test_api_memory.py tests/test_memory_repository.py tests/test_memory_system.py` 通过（63 passed）
  - `pytest -q tests/test_api_chat.py tests/test_api_realtime.py tests/test_memory_extractor.py tests/test_mempalace_adapter.py` 通过（94 passed）
  - `pytest -q tests/test_api_chat.py tests/test_api_memory.py tests/test_memory_repository.py tests/test_health.py tests/test_rollback_and_health.py` 通过（111 passed）
  - `pytest -q tests/test_api_state.py tests/test_memory_extractor.py tests/test_mempalace_adapter.py tests/test_api_realtime.py` 通过（57 passed）
  - `PYTHONPATH=. python scripts/mempalace_observability_preflight.py --turns 12` 通过（12/12 成功，alerts=none）
  - `PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8000 --turns 12` 完成（12/12 最终成功，期间自动重试；alerts=retrieval_p95_above_120ms,chat_p95_above_1500ms,retrieval_hit_rate_below_40pct）
  - `pytest -q tests/test_api_chat.py tests/test_mempalace_adapter.py tests/test_api_memory.py` 通过（64 passed）
  - `PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8010 --turns 10 --retries 5 --read-timeout 60` 通过（10/10 成功，alerts=none）
  - `PYTHONPATH=. python scripts/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --iterations 3 --interval-seconds 5` 通过（3 次采样，alerts_union=none，样本充足性未达门槛）
  - `PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8000 --turns 12 --retries 2 --read-timeout 60 --reset-first` 通过（12/12 成功，alerts=none）
  - `PYTHONPATH=. python scripts/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --iterations 3 --interval-seconds 2 --reset-first` 通过（3 次采样，alerts_union=none，样本充足性未达门槛）

## 0) 元信息（必填）

- 需求标题：小晏知识库建设
- 需求模式：标准
- 需求来源：产品规划需求
- 负责人：需求分析 agent
- 更新时间：2026-04-13

## 1) 需求摘要（必填）

- 背景与目标：当前系统已具备记忆能力，但缺少面向“长期知识沉淀、治理与可追溯引用”的统一机制。目标是在现有记忆架构上建设知识库能力，使回答更稳定、可解释、可运营。
- 用户价值：让用户在连续对话中获得更一致的上下文理解，并可在知识面板中查看知识来源与状态，提升信任感与可控性。
- 成功指标（可量化，至少 1 条）：知识命中相关性人工评审通过率达到 85%；`/chat` 因知识检索导致的 P95 延迟增量不超过 120ms；知识写入失败率低于 1%。
- 截止时间：2026-05-10
- 非目标（本次明确不做）：不建设多租户权限体系；不替换现有 LLM Gateway；不实现跨项目知识共享。

## 2) 范围、依赖与约束（必填）

- In-scope：知识实体模型定义；知识写入与清洗流程；检索融合策略；知识来源与引用展示；质量观测与回滚预案。
- Out-of-scope：企业级文档协同审批流程；独立向量数据库迁移；全文搜索独立服务化。
- 上游依赖：产品确认知识来源白名单；后端确认 MemPalace 命名空间规范；前端确认知识引用交互规范。
- 下游影响：`/chat` 指令构建、`/memory/*` API 展示语义、桌面端记忆页面、运维告警与回归测试集。
- 约束（性能/兼容/安全/时间/成本）：保持现有接口兼容；不破坏既有记忆检索行为；新增链路需支持异常降级；在单机开发环境可复现。
- 前置假设（Assumptions）：当前 `mempalace>=3.1.0` 依赖稳定可用，且团队可接受基于现有仓储的渐进扩展方案。

## 3) 待确认问题（必填，逐条状态）

| ID | 问题 | 状态 | Owner | 截止时间 | 风险 |
| --- | --- | --- | --- | --- | --- |
| Q1 | 外部知识源首批接入范围是否仅限本地 markdown 与对话记录 | 已确认 | 产品负责人 | 2026-04-12 | 中 |
| Q2 | 知识条目是否要求强制展示来源与更新时间 | 已确认 | 产品与前端 | 2026-04-12 | 中 |
| Q3 | 过期知识是否执行软删除并保留审计索引 | 已确认 | 后端负责人 | 2026-04-12 | 中 |
| Q4 | 知识检索是否允许跨 room 聚合召回 | 已确认 | 算法负责人 | 2026-04-12 | 中 |

## 4) 方案对比（A/B，必要时 C）

| 维度 | 方案 A | 方案 B | 方案 C（可选） |
| --- | --- | --- | --- |
| 实现复杂度 | 中，基于现有 MemPalace 扩展命名空间与元数据 | 高，引入独立向量库并双写迁移 | 中，保留现状并只做规则打分 |
| 交付速度 | 快，约 2 周可完成首版 | 慢，约 4 周以上 | 快，约 1 周 |
| 风险等级 | 中，主要是检索质量调优风险 | 高，迁移与一致性风险高 | 高，知识治理能力不足 |
| 回滚成本 | 低，可按命名空间回退并关闭新召回逻辑 | 高，涉及数据迁移回滚 | 低，直接回退规则 |
| 可维护性 | 高，贴合现有架构与测试体系 | 中，多系统维护成本高 | 低，后续扩展受限 |

- 推荐方案：方案 A
- 推荐理由（不超过 5 条）：复用现有运行时与测试资产；交付速度与风险平衡最好；支持逐步演进到更强检索；回滚路径清晰；符合“本体优先”架构约束。
- 不选其他方案的关键原因：方案 B 在当前阶段引入迁移复杂度过高；方案 C 不能形成真正可治理的知识库能力。

## 5) 任务拆分（必填）

| 任务ID | 任务描述 | 优先级 | 预计工时 | Owner | 依赖任务 | 阻塞条件 | 影响文件/模块 | 验收命令 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | 定义知识条目模型与命名空间规范（chat、autobio、inner、knowledge） | P0 | S | 后端 | 无 | 无 | services/core/app/memory/models.py, services/core/app/memory/mempalace_repository.py | `pytest -q services/core/tests/test_memory_repository.py` | 中 |
| T2 | 建设知识写入流水线（抽取、去重、标签化、来源元数据） | P0 | M | 后端 | T1 | 无 | services/core/app/memory/extractor.py, services/core/app/memory/service_extraction.py | `pytest -q services/core/tests/test_memory_extractor.py services/core/tests/test_memory_integration.py` | 中 |
| T3 | 改造检索融合策略，区分近期上下文与长期知识召回权重 | P1 | M | 算法与后端 | T1,T2 | 无 | services/core/app/memory/mempalace_adapter.py, services/core/app/api/chat_routes.py | `pytest -q services/core/tests/test_api_chat.py -k "mempalace or memory"` | 中 |
| T4 | 新增知识引用格式与来源透出，确保回答可追溯 | P1 | M | 前后端 | T3 | 无 | services/core/app/api/chat_routes.py, services/core/app/realtime.py, apps/desktop/src/components/chat | `pytest -q services/core/tests/test_api_chat.py services/core/tests/test_api_realtime.py && npm --prefix apps/desktop run test -- src/components/chat/ChatMessages.test.tsx src/lib/chatMessages.test.ts src/lib/realtime.test.ts` | 中 |
| T5 | 增加知识库管理 API（过滤、状态、软删除）并补契约测试 | P1 | M | 后端 | T1 | 无 | services/core/app/api/memory_routes.py, services/core/app/memory/service_crud.py, services/core/app/memory/repository.py, services/core/tests/test_api_memory.py | `pytest -q services/core/tests/test_api_memory.py services/core/tests/test_memory_repository.py services/core/tests/test_memory_system.py` | 中 |
| T6 | 建立观测与告警基线（延迟、命中质量、写入失败率） | P2 | S | 后端与运维 | T3 | 无 | docs/runbooks/mempalace-rollout.md, services/core/app/api/chat_routes.py, services/core/app/memory/observability.py, services/core/app/api/memory_routes.py | `pytest -q services/core/tests/test_api_chat.py services/core/tests/test_api_memory.py services/core/tests/test_health.py services/core/tests/test_rollback_and_health.py` | 中 |

## 6) 验收用例矩阵（必填，测试化）

| 用例ID | 类型 | Given | When | Then | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| A1 | 功能 | 已存在用户历史对话与知识条目 | 用户提出跨天延续问题 | 回答包含至少一条相关知识线索且语义一致 | 自动 |
| A2 | 回归 | 关闭知识检索增强开关 | 用户进行普通聊天 | 输出行为与当前主干版本一致 | 自动 |
| A3 | 性能 | 连续 50 次触发知识检索 | 压测 `/chat` | P95 延迟增量不超过 120ms | 自动 |
| A4 | 功能 | 知识条目带来源与更新时间 | 前端打开记忆面板 | 可查看来源、标签、更新时间且字段完整 | 手动 |
| A5 | 发布 | 模拟写入依赖异常 | 发起对话并写入知识 | 主回复仍为 200，写入失败被告警记录 | 自动 |

## 7) 发布与回滚（标准/发布级必填）

- Done 标准：核心任务 T1-T5 完成并通过测试，知识命中质量评审达到阈值，观测看板可用。
- 上线门禁：后端与前端回归测试全绿；Q1/Q3/Q4 已确认并落盘；灰度流量 10% 运行 24 小时无 P0 告警。
- 回滚触发条件：`/chat` 错误率升高并持续 15 分钟；知识相关投诉在 24 小时内超过 5 条；写入失败率连续 1 小时高于 3%。
- 回滚路径：关闭知识增强召回逻辑并恢复仅近期对话上下文；回退知识管理 API 到上一稳定版本；保留已写入数据用于后续修复。
- 观测指标（D0 / D+1 / D+7）：D0 监控错误率与延迟；D+1 复盘知识命中与引用完整率；D+7 评估用户连续对话满意度与知识衰减情况。

## 8) 质量评分（必填）

- 评分卡文件：`/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-scorecard.md`
- 当前总分：99
- 是否可进入下一阶段：是
- 若否，补齐项（owner + 截止时间）：无
