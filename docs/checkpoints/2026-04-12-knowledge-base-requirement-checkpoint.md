# 断点续跑：知识库建设需求分析

## 1) 会话快照

- 任务标题：小晏知识库建设
- 技能类型：需求
- 当前模式：标准
- 当前阶段：灰度观察中（T1-T6 已完成，二轮复验通过，reset-first 口径已建立）
- 更新时间：2026-04-13
- 负责人：需求分析 agent

## 2) 当前状态

- 已完成：
  - [x] 完成知识预热并确认现有记忆架构约束
  - [x] 输出结构化需求文档与评分卡
  - [x] 生成评审会决策包（D1-D3）
  - [x] 确认 D1-D3 并回填 Q1/Q3/Q4 状态
  - [x] 完成 T1（知识字段与命名空间校验）并通过相关测试
  - [x] 完成 T2（抽取、去重、标签化、来源元数据）并通过相关测试
  - [x] 完成 T3（检索融合权重策略）并通过相关测试
  - [x] 完成 T4（知识引用透出：后端事件 + 前端展示）并通过相关测试
  - [x] 完成 T5（知识管理 API：过滤/软删除/恢复）并通过相关测试
  - [x] 完成 T6（观测与告警基线：延迟/命中质量/写入失败率）并通过相关测试
  - [x] 完成灰度前自动验收（12 轮预验收 + observability 证据落盘）
  - [x] 完成真实流量灰度首轮验收（12 轮 HTTP 实流量 + observability 证据落盘）
  - [x] 完成告警闭环改造（跨 room 长期源探测 + 小样本告警门槛）
  - [x] 完成真实流量灰度二轮复验（10/10 成功，alerts=none）
  - [x] 启动 24h 灰度观察并产出首个 watch 基线证据
  - [x] 增加 observability reset 能力并完成 reset-first 验收证据
  - [x] 运行需求产物校验脚本并通过
- 进行中：
  - [ ] 持续采样直至样本充足性达标（latency/write/quality >= 20）
- 下一步（唯一）：
  - [ ] 完成 10% 流量 24 小时灰度观察并输出最终上线门禁结论（含样本充足性）

## 3) 质量评分（v2 必填）

- 完整性（0-25）：25
- 可执行性（0-25）：25
- 可验收性（0-25）：25
- 风险覆盖（0-25）：24
- 总分（0-100）：99
- 当前门禁是否通过：是

## 4) 关键结论与决策

- 决策 1：采用标准模式推进需求分析
  - 原因：涉及跨模块协作与上线风险，需要方案对比和测试化验收
  - 影响：需求文档必须包含发布与回滚章节
- 决策 2：优先选择基于现有 MemPalace 的扩展方案
  - 原因：交付速度和维护成本最佳，符合当前架构信条
  - 影响：后续实施重点放在命名空间治理和召回质量优化

## 5) 变更与证据

- 涉及文件：
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-construction.md`
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-review-pack.md`
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-scorecard.md`
  - `/Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-12-knowledge-base-requirement-checkpoint.md`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/models.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/mempalace_repository.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/repository.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/service_crud.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/api/memory_routes.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/observability.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/extractor.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/mempalace_adapter.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/api/chat_routes.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/realtime.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/runtime_ext/bootstrap.py`
  - `/Users/ldy/Desktop/map/ai/services/core/scripts/mempalace_observability_preflight.py`
  - `/Users/ldy/Desktop/map/ai/services/core/scripts/mempalace_live_observability_preflight.py`
  - `/Users/ldy/Desktop/map/ai/services/core/scripts/mempalace_observability_watch.py`
  - `/Users/ldy/Desktop/map/ai/services/core/app/memory/observability.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_memory_repository.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_memory_extractor.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_mempalace_adapter.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_api_chat.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_api_realtime.py`
  - `/Users/ldy/Desktop/map/ai/services/core/tests/test_api_memory.py`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/App.tsx`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/components/chat/ChatMessages.tsx`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/components/chat/chatTypes.ts`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/lib/chatMessages.ts`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/lib/realtime.ts`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/styles/chat/chat-message.css`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/components/chat/ChatMessages.test.tsx`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/lib/chatMessages.test.ts`
  - `/Users/ldy/Desktop/map/ai/apps/desktop/src/lib/realtime.test.ts`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/mempalace-rollout.md`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-preflight-20260412-170435.json`
- 执行命令与结果：
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_memory_repository.py` 通过（8 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_domain_models.py` 通过（2 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_memory_extractor.py` 通过（36 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_memory_integration.py tests/test_memory_system.py` 通过（61 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_mempalace_adapter.py` 通过（13 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_chat.py -k "mempalace or splits_recent_and_long_term_context_budget"` 通过（6 passed, 34 deselected）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_chat.py` 通过（40 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_realtime.py tests/test_api_chat.py` 通过（45 passed）
  - `cd /Users/ldy/Desktop/map/ai && npm --prefix apps/desktop run test -- src/components/chat/ChatMessages.test.tsx src/lib/chatMessages.test.ts src/lib/realtime.test.ts` 通过（8 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_memory.py tests/test_memory_repository.py tests/test_memory_system.py` 通过（63 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_chat.py tests/test_api_realtime.py tests/test_memory_extractor.py tests/test_mempalace_adapter.py` 通过（94 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_chat.py tests/test_api_memory.py tests/test_memory_repository.py tests/test_health.py tests/test_rollback_and_health.py` 通过（111 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_state.py tests/test_memory_extractor.py tests/test_mempalace_adapter.py tests/test_api_realtime.py` 通过（57 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_observability_preflight.py --turns 12` 通过（12/12 成功，alerts=none）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8000 --turns 12` 完成（12/12 最终成功；alerts=retrieval_p95_above_120ms,chat_p95_above_1500ms,retrieval_hit_rate_below_40pct）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_chat.py tests/test_mempalace_adapter.py tests/test_api_memory.py` 通过（64 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8010 --turns 10 --retries 5 --read-timeout 60` 通过（10/10 成功；alerts=none）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --iterations 3 --interval-seconds 5` 通过（3 次采样；alerts_union=none；data_sufficiency=false）
  - `cd /Users/ldy/Desktop/map/ai/services/core && pytest -q tests/test_api_memory.py tests/test_api_chat.py tests/test_mempalace_adapter.py` 通过（65 passed）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_live_observability_preflight.py --base-url http://127.0.0.1:8000 --turns 12 --retries 2 --read-timeout 60 --reset-first` 通过（12/12 成功；alerts=none）
  - `cd /Users/ldy/Desktop/map/ai/services/core && PYTHONPATH=. python scripts/mempalace_observability_watch.py --base-url http://127.0.0.1:8000 --iterations 3 --interval-seconds 2 --reset-first` 通过（3 次采样；alerts_union=none；data_sufficiency=false）
  - `/Users/ldy/.codex/skills/requirement-workflow/scripts/validate_requirement_artifacts.sh --mode standard --requirement /Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-construction.md --checkpoint /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-12-knowledge-base-requirement-checkpoint.md --scorecard /Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-scorecard.md` 通过
- 关键日志/截图/报告路径：
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-construction.md`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-preflight-20260412-170435.json`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-171217.json`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-173408.json`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-gray-watch-20260412-174025.json`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-live-preflight-20260412-180042.json`
  - `/Users/ldy/Desktop/map/ai/docs/runbooks/evidence/mempalace-gray-watch-20260412-180200.json`

## 6) 风险与阻塞

- 风险：
  - 当前数据集中尚无 `knowledge/autobio` 等跨 room 长期源时，长期检索将自动跳过（对应 quality 查询样本为 0）
  - MiniMax 高速模型在当前账号额度下不可用（`your current token plan not support model`），灰度阶段仍需使用 deepseek 配置
  - T3 检索融合策略若阈值配置不当，可能引入召回质量波动
  - T5 软删除与审计索引并行时需防止存储膨胀
- 阻塞：
  - 暂无硬阻塞
- 需要谁确认：
  - 无

## 7) 续跑指令（下次直接用）

- 建议提示词（长版）：
  - `继续这个任务，先读取 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-12-knowledge-base-requirement-checkpoint.md，按“下一步（唯一）”执行，并按模式要求更新断点和评分。`
- 若需要子agent：
  - `基于 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-12-knowledge-base-requirement-checkpoint.md 拆分并并行执行未完成项，回传统一格式（结论、风险、评分、下一步唯一）。`
