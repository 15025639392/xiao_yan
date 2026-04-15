# 标准模式需求：apps/desktop Chat MCP 能力接入

## 结论

- 该需求适合标准模式，涉及 `apps/desktop` 前端、`services/core` 聊天路由、运行时配置与测试基线的跨模块改造。
- 推荐采用“Core 统一编排 MCP + Desktop 仅做配置与发起”的方案，复用现有 `/chat` 工具回路与实时事件链路，降低分叉风险。
- 当前代码基线已确认：`/chat` 仅有 file tools 与 skills 注入，尚无 MCP server 管理、tool catalog 注入和调用执行链路。
- 本轮需求可进入实现阶段，但 Q1 与 Q2 需在实现开始前完成确认，避免协议选型返工。

## 下一步（唯一）

- 召开 30 分钟技术评审，锁定 Q1（MCP 传输协议）和 Q2（高风险 MCP tool 审批策略），评审结论直接回填本需求文档后开工 T1。

## 产物路径

- `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-construction.md`

## 知识预热（必须）

- 已掌握的关键约束：
  - 前端 chat 发送链路位于 `apps/desktop/src/App.tsx`，当前 `ChatRequestBody` 仅包含 `message`、`attachments`，不含 MCP 字段。
  - 后端 `/chat` 在 `services/core/app/api/chat_routes.py` 中实现，`_run_chat_submission_with_tools` 目前仅注入 `CHAT_FILE_TOOL_DEFINITIONS`。
  - 后端 `ChatRequest` 在 `services/core/app/llm/schemas.py` 中已有 `skills` 字段，说明请求契约可继续扩展。
  - 运行时配置由 `services/core/app/runtime_ext/runtime_config.py` 管理，当前有 chat model 与 folder permissions，但无 MCP 相关配置。
  - 桌面配置面板位于 `apps/desktop/src/components/chat/ChatConfigPanel.tsx`，具备新增配置区块的现成入口。
- 需要用户确认的未知项（逐条）：
  - Q1: MCP server 首期只支持 `stdio` 还是同时支持 `sse/http`。
  - Q2: MCP tool 是否统一走审批，还是仅对写操作与命令执行类 tool 审批。
  - Q3: 是否允许用户在桌面端自定义 MCP server 启动命令。
- 可能的技术风险点：
  - 协议层不收敛会导致后端执行器抽象重复实现。
  - MCP tool 回调超时会拖慢 `/chat`，需要明确降级与断路策略。
  - 直接暴露高权限 MCP tool 可能绕过当前 folder/capability 边界，需要并入现有策略。
- 统一流水线接线声明：
  - 已确认需求作业流下一轮 failing test 选择仍由 `../skill-self-evolution/scripts/run_skill_self_evolution_pipeline.sh` 统一收敛，本轮仅新增需求产物，不引入独立演进分叉。

## 0) 元信息（必填）

- 需求标题：apps/desktop Chat MCP 能力接入
- 需求模式：标准
- 需求来源：产品需求 `需求:为apps/desktop 的/chat接入mcp能力`
- 负责人：需求分析 agent
- 更新时间：2026-04-13

## 1) 需求摘要（必填）

- 背景与目标：当前 chat 仅支持文件工具与 skills 注入，无法接入标准 MCP server 的工具生态；目标是在不破坏现有 `/chat` 流程前提下，让 desktop chat 可配置并使用 MCP 工具回答。
- 用户价值：用户可在同一 chat 界面调用外部系统能力，减少手动切换工具与复制上下文。
- 成功指标（可量化，至少 1 条）：首期支持至少 2 个 MCP server 同时可用、`/chat` 请求成功率不低于 99%、MCP 启用后 `/chat` P95 延迟增量不超过 350ms、MCP tool 失败降级成功率达到 100%。
- 截止时间：2026-04-20
- 非目标（本次明确不做）：不做 MCP marketplace，不做多租户隔离与权限继承体系，不做移动端同步配置。

## 2) 范围、依赖与约束（必填）

- In-scope：
  - 扩展 chat 请求与配置契约，支持 MCP server 选择与启停。
  - Core 注入 MCP tool catalog 到 `/chat` 工具回路，并实现 tool call 执行与结果回传。
  - Desktop Chat 配置面板支持 MCP server 列表展示、启用状态与基础错误提示。
  - 覆盖前后端关键回归测试与失败降级测试。
- Out-of-scope：
  - MCP server 生命周期托管平台。
  - MCP 使用计费与额度看板。
  - 非 chat 场景（orchestrator、tools 页）的统一接入。
- 上游依赖：
  - 协议决策（Q1）与审批策略（Q2）确认。
  - 目标 MCP server 提供可稳定访问的 schema 与健康检查能力。
- 下游影响：
  - `services/core/app/api/chat_routes.py`、`services/core/app/llm/schemas.py`、`apps/desktop/src/lib/api.ts`、`apps/desktop/src/components/chat/*`。
- 约束（性能/兼容/安全/时间/成本）：
  - 保持现有 `/chat` 请求向后兼容，老请求体无需修改即可继续工作。
  - 必须保留当前 file tools 回路与 fallback 逻辑。
  - MCP tool 风险分级需映射到现有 capability/risk 模型。
- 前置假设（Assumptions）：
  - 首期以 desktop 本地环境为主，MCP server 可由客户端或 core 可达路径启动。

## 3) 待确认问题（必填，逐条状态）

| ID | 问题 | 状态 | Owner | 截止时间 | 风险 |
| --- | --- | --- | --- | --- | --- |
| Q1 | 首期 MCP 传输协议范围是否只做 `stdio` | 待确认 | 技术负责人 | 2026-04-14 | 高 |
| Q2 | MCP tool 审批策略是否采用“写操作和命令执行强制审批” | 待确认 | 安全负责人 | 2026-04-14 | 高 |
| Q3 | 用户是否可在 desktop 自定义 server 启动命令 | 待确认 | 产品负责人 | 2026-04-15 | 中 |
| Q4 | 默认内置 MCP server 白名单是否包含 file-system 与 git | 有风险假设 | 产品负责人 | 2026-04-15 | 中 |

## 4) 方案对比（A/B，必要时 C）

| 维度 | 方案 A | 方案 B | 方案 C（可选） |
| --- | --- | --- | --- |
| 实现复杂度 | 中：Core 统一 MCP 编排，Desktop 负责配置与请求参数 | 高：Desktop 直连 MCP，Core 仅透传文本 | 低：仅做提示词注入，不接真实 MCP |
| 交付速度 | 中：约 5 个工作日 | 慢：约 8 个工作日 | 快：约 2 个工作日 |
| 风险等级 | 中：集中治理，回路可复用 | 高：前后端双栈协议分叉 | 高：用户预期与真实能力不一致 |
| 回滚成本 | 低：关闭 MCP 开关即可退回 file tools | 中：需回退前端直连逻辑与缓存状态 | 低：删除注入逻辑 |
| 可维护性 | 高：单入口治理工具与审批 | 中：调试链路分散 | 低：不可扩展 |

- 推荐方案：方案 A
- 推荐理由（不超过 5 条）：
  - 与现有 `/chat` 工具循环模型一致，减少新概念。
  - 安全与审批策略可复用 capability 风险模型。
  - 回滚简单，关闭 MCP 不影响现有 file tools。
  - 桌面端改造集中在配置与请求体，风险可控。
  - 测试覆盖边界清晰，易于分层验收。
- 不选其他方案的关键原因：方案 B 会形成 Core 与 Desktop 双执行中心并显著提高后续演进成本，方案 C 仅做提示注入无法满足真实 MCP 接入目标。

## 5) 任务拆分（必填）

| 任务ID | 任务描述 | 优先级 | 预计工时 | Owner | 依赖任务 | 阻塞条件 | 影响文件/模块 | 验收命令 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | 扩展 chat 请求与 schema，新增 `mcp_servers` 字段并保持向后兼容 | P0 | S | 后端 | 无 | Q1 未确认 | `services/core/app/llm/schemas.py`, `apps/desktop/src/lib/api.ts` | `cd services/core && pytest -q tests/test_api_chat.py -k "schema or chat"` | 中 |
| T2 | 设计并实现 MCP server 配置读写接口与运行时配置存储 | P0 | M | 后端 | T1 | Q1 未确认 | `services/core/app/runtime_ext/runtime_config.py`, `services/core/app/api/chat_routes.py`, `services/core/app/api/config_routes.py` | `cd services/core && pytest -q tests/test_api_config.py tests/test_api_chat.py -k "mcp"` | 中 |
| T3 | 在 `/chat` 工具回路中注入 MCP tool catalog，并支持 call-output 回传 | P0 | L | 后端 | T1,T2 | Q2 未确认 | `services/core/app/api/chat_routes.py`, `services/core/app/llm/gateway.py` | `cd services/core && pytest -q tests/test_api_chat.py -k "tool or mcp"` | 高 |
| T4 | desktop chat 配置面板新增 MCP 区块（列表、启用、错误态） | P1 | M | 前端 | T1,T2 | Q3 未确认 | `apps/desktop/src/components/chat/ChatConfigPanel.tsx`, `apps/desktop/src/components/chat/useChatPanelState.ts` | `cd apps/desktop && npm run test -- src/components/chat/ChatConfigPanel.test.tsx` | 中 |
| T5 | chat 发送链路携带 MCP 选择并支持重试保持原请求体 | P1 | M | 前端 | T1,T4 | 无 | `apps/desktop/src/App.tsx`, `apps/desktop/src/components/chat/chatTypes.ts` | `cd apps/desktop && npm run test -- src/App.test.tsx src/lib/api.test.ts` | 中 |
| T6 | 增加失败降级与观测埋点（超时、不可达、审批拒绝） | P1 | M | 前后端 | T3,T5 | Q2 未确认 | `services/core/app/api/chat_routes.py`, `apps/desktop/src/components/chat/ChatMessages.tsx` | `cd services/core && pytest -q tests/test_api_chat.py && cd /Users/ldy/Desktop/map/ai/apps/desktop && npm run test -- src/components/chat/ChatMessages.test.tsx` | 中 |

## 6) 验收用例矩阵（必填，测试化）

| 用例ID | 类型 | Given | When | Then | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| A1 | 功能 | 已配置并启用 1 个 MCP server | 用户发送 chat 请求并命中该 tool | assistant 返回包含 MCP tool 结果的完整回答 | 自动 |
| A2 | 回归 | 未配置任何 MCP server | 用户发送普通 chat | 行为与当前主干一致，file tools 不受影响 | 自动 |
| A3 | 性能 | 开启 MCP 且工具可用 | 连续执行 30 次 chat 请求 | P95 延迟增量不超过 350ms | 自动 |
| A4 | 发布 | MCP server 不可达 | 用户发送 chat | 系统降级为无 MCP 回答，不出现空响应 | 自动 |
| A5 | 功能 | 用户在 desktop 修改 MCP 启用状态 | 点击保存并重新发送 chat | 后端收到的 `mcp_servers` 与 UI 选择一致 | 自动 |
| A6 | 回归 | 用户触发“重试上一条消息” | 点击重试 | 重试请求保留原 `mcp_servers` 与附件参数 | 自动 |

## 7) 发布与回滚（标准/发布级必填）

- Done 标准：
  - T1-T6 完成并通过对应自动化测试。
  - Q1-Q2 均已确认并回填。
  - 灰度期间无 P0 级安全与可用性告警。
- 上线门禁：`tests/test_api_chat.py` 与前端 chat 关键测试全绿，A4 降级用例连续 3 次稳定通过，审批策略在 capability 审计日志可追溯。
- 回滚触发条件：MCP 启用后 `/chat` 错误率连续 10 分钟高于 2%，或出现绕过审批的高风险调用，或空响应比例超过 1%。
- 回滚路径：将 `chat_mcp_enabled` 设为 `false`，`/chat` 工具注入回退到 `CHAT_FILE_TOOL_DEFINITIONS`，前端隐藏 MCP 配置区块并保留历史配置。
- 观测指标（D0 / D+1 / D+7）：D0 监控 `chat_error_rate`、`mcp_call_timeout_rate`、`empty_response_rate`；D+1 监控 `mcp_tool_success_rate`、`mcp_fallback_count`；D+7 监控 `mcp_enabled_chat_ratio` 与用户重试率。

## 8) 质量评分（必填）

- 评分卡文件：`/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-scorecard.md`
- 当前总分：86
- 是否可进入下一阶段：是
- 若否，补齐项（owner + 截止时间）：无
