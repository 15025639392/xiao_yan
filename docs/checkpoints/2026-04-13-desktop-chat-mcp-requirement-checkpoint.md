# 断点续跑：apps/desktop Chat MCP 能力接入

## 1) 会话快照

- 任务标题：apps/desktop Chat MCP 能力接入
- 技能类型：需求
- 当前模式：标准
- 当前阶段：需求分析完成，待评审拍板
- 更新时间：2026-04-13
- 负责人：需求分析 agent

## 2) 当前状态

- 已完成：
  - [x] 完成知识预热并定位 chat 当前无 MCP 能力的代码事实
  - [x] 输出标准模式需求主文档（含 A/B 方案、任务拆分、验收矩阵）
  - [x] 输出评审包与评分卡
  - [x] 补齐待确认问题 owner 与截止时间
- 进行中：
  - [ ] 等待 D1-D3 技术评审拍板
- 下一步（唯一）：
  - [ ] 召开 30 分钟评审并回填 D1-D3 结论到需求主文档后，立即启动 T1

## 3) 质量评分（v2 必填）

- 完整性（0-25）：22
- 可执行性（0-25）：22
- 可验收性（0-25）：21
- 风险覆盖（0-25）：21
- 总分（0-100）：86
- 当前门禁是否通过：是

## 4) 关键结论与决策

- 决策 1：采用标准模式推进
  - 原因：涉及前后端与运行时配置的跨模块改造
  - 影响：必须包含发布与回滚章节以及测试化验收
- 决策 2：优先推荐 Core 统一 MCP 编排方案
  - 原因：兼容现有 `/chat` 工具回路且回滚成本低
  - 影响：desktop 侧仅承担配置和请求发起，不引入独立执行中心

## 5) 变更与证据

- 涉及文件：
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-construction.md`
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-review-pack.md`
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-scorecard.md`
  - `/Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-13-desktop-chat-mcp-requirement-checkpoint.md`
- 执行命令与结果：
  - `rg -n "mcp|/chat|skills" apps/desktop services/core -S`，确认当前 chat 主链路无 MCP 实现
  - `sed -n` 读取 `App.tsx`、`api.ts`、`chat_routes.py`、`runtime_config.py`，确认接入边界
  - `validate_requirement_artifacts.sh` 校验需求产物（本轮将执行）
- 关键日志/截图/报告路径：
  - `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-13-desktop-chat-mcp-construction.md`

## 6) 风险与阻塞

- 风险：
  - Q1 协议范围未拍板会影响执行器设计
  - Q2 审批策略未拍板会影响风险门禁与审计路径
- 阻塞：
  - 无硬阻塞，可先做协议无关的数据结构准备
- 需要谁确认：
  - 技术负责人、安全负责人、产品负责人

## 7) 续跑指令（下次直接用）

- 建议提示词（长版）：
  - `继续这个任务，先读取 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-13-desktop-chat-mcp-requirement-checkpoint.md，按“下一步（唯一）”执行，并按模式要求更新断点和评分。`
- 若需要子agent：
  - `基于 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-13-desktop-chat-mcp-requirement-checkpoint.md 拆分并并行执行未完成项，回传统一格式（结论、风险、评分、下一步唯一）。`
