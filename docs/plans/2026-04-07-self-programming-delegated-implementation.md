# 自我编程委托化实施计划（含开工审批 + 可配置冷却 + 理由/方向 + 拒绝流）

## Summary
- 主架构：弱智能体治理、Codex 专业执行、隔离 worktree。
- 四项硬能力：
  - 人工点击“确认开工”后才可执行。
  - 自我编程冷却时间可配置（分钟级）。
  - 任务必须填写“理由/方向”说明。
  - 支持拒绝（开工拒绝与晋升拒绝）。
- 目标：执行前可解释、执行中可控、执行后可审计。

## Implementation Changes
### Phase A（基础修复）
- 修复回滚 API 断裂：统一使用运行中的执行器实例与 `smart_rollback`。
- 统一 history 数据源：runtime/service/history API 同源。
- 预检 fail-close：沙箱预验证失败（含超时）直接阻断。

### Phase B（开工审批门禁）
- 状态流：`drafted -> pending_start_approval -> queued -> running -> completed|failed|frozen`。
- 未确认开工不得入队、不得触发 delegate runner。
- 支持 `reject-start`，拒绝后回到 `drafted` 并记录审计字段。

### Phase C（理由/方向必填）
- 任务模型新增：`reason_statement`、`direction_statement`。
- `request-start` 校验二者必填，缺失拒绝受理。
- 前端开工审批面板固定展示理由/方向。

### Phase D（冷却时间可配置）
- 新增 runtime 配置：
  - `self_programming_hard_failure_cooldown_minutes`
  - `self_programming_proactive_cooldown_minutes`
- 新增接口：
  - `GET /config/self-programming`
  - `PUT /config/self-programming`
- 任务创建时固化快照：`cooldown_policy_snapshot`，并计算 `cooldown_until`。

### Phase E（委托执行与拒绝流）
- 新增接口：
  - `POST /self-programming/{id}/request-start`
  - `POST /self-programming/{id}/approve-start`
  - `POST /self-programming/{id}/reject-start`
  - `POST /self-programming/{id}/delegate`
  - `POST /self-programming/{id}/retry`
  - `POST /self-programming/{id}/thaw`
  - `POST /self-programming/{id}/promote`
- `approve/reject` 继续作为晋升审批阶段接口。
- 历史返回增加理由/方向/拒绝轨迹字段。

### Phase F（前端可观测）
- 新增开工审批面板：`drafted/pending_start_approval/queued`。
- 新增冷却设置入口（分钟级）。
- 状态与历史展示补充理由/方向、拒绝信息、冷却快照。

## API / Interface Changes
### Backend
- 模型扩展：
  - `SelfProgrammingStatus` 新增：`drafted`、`pending_start_approval`、`queued`、`running`、`completed`、`frozen`。
  - `SelfProgrammingJob` 新增：
    - 理由/方向：`reason_statement`、`direction_statement`
    - 委托：`owner_type`、`delegate_provider`、`delegate_run_id`、`queue_status`、`execution_workspace`
    - 审计：`start_approval_reason`、`start_approved_by`、`start_approved_at`
    - 拒绝：`rejection_phase`、`rejection_reason`、`rejected_by`、`rejected_at`
    - 冷却快照：`cooldown_policy_snapshot`
- 路由扩展：开工审批、委托执行、冷却配置。

### Frontend
- `SelfProgrammingJob` 类型扩展：新增开工状态、理由/方向、拒绝审计、冷却快照字段。
- 新增 API 方法：
  - `requestStartSelfProgrammingJob`
  - `approveStartSelfProgrammingJob`
  - `rejectStartSelfProgrammingJob`
  - `delegateSelfProgrammingJob`
  - `fetchSelfProgrammingConfig`
  - `updateSelfProgrammingConfig`

## Test Plan & Acceptance
### 单测覆盖
- 理由/方向缺失时 `request-start` 失败。
- `approve-start` 后状态转 `queued` 并落审计字段。
- `reject-start` 记录拒绝阶段与拒绝原因。
- `delegate` 对非 `queued` 状态拒绝。
- 冷却配置 API 可读可写且空 patch 拒绝。
- planner 使用 runtime 冷却配置并写入快照。

### 集成验收
- 后端：`services/core` 全量测试通过。
- 前端：`apps/desktop` 全量测试通过。
- 开工门禁 + 冷却配置 + 理由/方向 + 拒绝流可端到端跑通。

## 完成状态
- [x] Phase A
- [x] Phase B
- [x] Phase C
- [x] Phase D
- [x] Phase E
- [x] Phase F

## 证据命令
- `cd services/core && pytest -q`
- `cd apps/desktop && npm test -- --run`

## 风险项
- 当前“异步队列”采用状态驱动 + 手动 `delegate` 触发，尚未引入独立持久任务队列 worker；后续可升级为真正后台 worker。
- `promote` 当前实现为状态门禁标记，尚未对接跨 worktree 的自动 cherry-pick/merge 策略。
