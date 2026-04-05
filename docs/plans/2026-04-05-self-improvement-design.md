# 自我编程能力 设计

## 目标

让数字人在检测到自身实现不够有效时，能以独立运行态进入一次受控的自我编程流程，在当前仓库内生成小范围补丁、执行测试验证，并将结果回写到运行状态与前端展示。

## 范围

- 允许修改当前仓库的应用层代码。
- 自我编程必须经过测试门禁，测试通过才保留改动。
- 失败触发强制进入，主动优化允许低频触发。
- 第一版不允许修改执行沙箱、自动提交 git、安装外部依赖或做大范围重构。

## 状态机

- `focus_mode` 新增 `self_improvement`。
- `BeingState` 新增 `self_improvement_job`。
- `self_improvement_job.status` 使用 `pending -> diagnosing -> patching -> verifying -> applied | failed`。
- 自我编程期间暂停常规自治；完成或失败后回到 `autonomy`。

## 触发规则

- 硬信号：测试失败、连续无效推进、明确能力缺口。
- 软信号：重复空泛回答、计划质量低、行动结果无增量、频繁依赖用户推动。
- 自我反思文本只能解释触发原因，不能单独触发。
- 主动优化受 cooldown 限制。

## 执行闭环

1. `diagnosing`：生成最小改进规格与目标测试清单。
2. `patching`：生成并应用小范围补丁，记录 touched files。
3. `verifying`：运行目标测试与相关回归测试。
4. `applied`：测试通过后保留改动，回写状态、记忆和结果摘要。
5. `failed`：测试失败或补丁失败，记录原因并退出。

## 架构

- `app/self_improvement/models.py`：定义 job、状态、验证结果。
- `app/self_improvement/evaluator.py`：决定是否触发和触发原因。
- `app/self_improvement/planner.py`：把触发原因转换成小范围编码任务。
- `app/self_improvement/executor.py`：应用补丁、执行测试、收集结果。
- `app/self_improvement/service.py`：给 `AutonomyLoop` 提供统一入口。

## 展示

- `/state` 直接暴露 `self_improvement_job`。
- 前端状态面板新增“她刚刚为什么改自己 / 改了什么 / 验证结果”。

## 第一版实现策略

- 先只实现一个可验证的自改目标：补足或修复测试驱动的小型应用层改动。
- 自我编程以模板化改进 spec 为主，不追求开放式任意重构。
- 优先保证链路闭合、状态可见、验证真实。
