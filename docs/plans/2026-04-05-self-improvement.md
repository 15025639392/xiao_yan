# 自我编程能力 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让数字人在检测到自身能力不足时，能进入受控的自我编程流程，在当前仓库内完成小范围代码修改、测试验证与状态回写。

**Architecture:** 新增独立的 `self_improvement` 运行态和 `self_improvement_job` 数据模型，由 `AutonomyLoop` 在失败触发或低频主动触发时启动。自我编程流程拆为 evaluator、planner、executor 三段，先产出最小改进规格，再执行小范围补丁和目标测试，最后把验证结果暴露给 API 和前端。

**Tech Stack:** FastAPI, React, Python, pytest, Vitest

---

### Task 1: 建立自我编程状态模型

**Files:**
- Modify: `services/core/tests/test_domain_models.py`
- Modify: `services/core/tests/test_runtime.py`
- Modify: `services/core/app/domain/models.py`
- Modify: `services/core/app/runtime.py`

**Step 1: 写失败测试**

补测试覆盖：
- `focus_mode` 支持 `self_improvement`
- `BeingState.default()` 默认没有 `self_improvement_job`
- `StateStore` 能持久化和恢复 `self_improvement_job`

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_domain_models.py tests/test_runtime.py -v`
Expected: FAIL，失败点落在状态模型缺少自我编程字段。

**Step 3: 写最小实现**

- 在 `services/core/app/domain/models.py` 新增 `SelfImprovementJob` 相关模型
- 扩展 `FocusMode`
- 让 `StateStore` 正确恢复新字段

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_domain_models.py tests/test_runtime.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/tests/test_domain_models.py services/core/tests/test_runtime.py services/core/app/domain/models.py services/core/app/runtime.py docs/plans/2026-04-05-self-improvement-design.md docs/plans/2026-04-05-self-improvement.md
git commit -m "feat: 添加自我编程状态模型"
```

### Task 2: 接入自检与自主循环

**Files:**
- Create: `services/core/app/self_improvement/models.py`
- Create: `services/core/app/self_improvement/evaluator.py`
- Create: `services/core/app/self_improvement/planner.py`
- Create: `services/core/app/self_improvement/service.py`
- Modify: `services/core/tests/test_autonomy_loop.py`
- Modify: `services/core/app/agent/loop.py`

**Step 1: 写失败测试**

补测试覆盖：
- 硬信号触发时，`AutonomyLoop` 进入 `self_improvement`
- 主动优化仅在 cooldown 允许时触发
- 进入自我编程后暂停常规 autonomy thought

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: FAIL，失败点落在缺少自检触发与新状态切换。

**Step 3: 写最小实现**

- 实现 evaluator 的硬信号 / 软信号判断
- 实现 planner 生成最小 spec 与测试清单
- 在 `AutonomyLoop` 中优先推进 `self_improvement_job`

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/self_improvement/models.py services/core/app/self_improvement/evaluator.py services/core/app/self_improvement/planner.py services/core/app/self_improvement/service.py services/core/tests/test_autonomy_loop.py services/core/app/agent/loop.py
git commit -m "feat: 接入自我编程触发与状态机"
```

### Task 3: 实现受控补丁与测试执行

**Files:**
- Create: `services/core/app/self_improvement/executor.py`
- Modify: `services/core/tests/test_autonomy_loop.py`
- Modify: `services/core/tests/test_api_state.py`
- Modify: `services/core/app/main.py`
- Modify: `services/core/app/agent/loop.py`

**Step 1: 写失败测试**

补测试覆盖：
- 自我编程 job 能从 `patching` 进入 `verifying`
- 测试通过后状态变为 `applied`
- 测试失败后状态变为 `failed`
- `/state` 返回 `self_improvement_job`

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_autonomy_loop.py tests/test_api_state.py -v`
Expected: FAIL，失败点落在缺少 executor 和 API 暴露。

**Step 3: 写最小实现**

- 新增受控 executor，支持模板化补丁应用与测试命令执行
- 记录 patch summary、verification、cooldown
- 在 `main.py` 维持依赖装配与状态输出

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_autonomy_loop.py tests/test_api_state.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/self_improvement/executor.py services/core/tests/test_autonomy_loop.py services/core/tests/test_api_state.py services/core/app/main.py services/core/app/agent/loop.py
git commit -m "feat: 添加自我编程执行与验证闭环"
```

### Task 4: 前端展示自我编程状态

**Files:**
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/components/StatusPanel.tsx`
- Modify: `apps/desktop/src/components/StatusPanel.test.tsx`
- Modify: `apps/desktop/src/App.test.tsx`

**Step 1: 写失败测试**

补测试覆盖：
- 状态面板展示当前自我编程阶段、原因、目标模块和验证结果
- 自我编程完成后展示最近一次结果摘要

**Step 2: 运行测试并确认失败**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx`
Expected: FAIL，失败点落在状态类型和 UI 未展示新字段。

**Step 3: 写最小实现**

- 扩展前端状态类型
- 在状态面板渲染自我编程区域

**Step 4: 运行测试并确认通过**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx`
Expected: PASS

**Step 5: 提交**

```bash
git add apps/desktop/src/lib/api.ts apps/desktop/src/components/StatusPanel.tsx apps/desktop/src/components/StatusPanel.test.tsx apps/desktop/src/App.test.tsx
git commit -m "feat: 展示自我编程状态"
```

### Task 5: 全量验证

**Files:**
- Modify: `services/core/tests/test_api_lifecycle.py`
- Modify: `services/core/tests/test_api_chat.py`

**Step 1: 写失败测试**

补测试覆盖：
- 自我编程完成后的状态能被 chat / lifecycle 正确感知
- 自我编程失败不会破坏现有 morning plan 与 autonomy 链路

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_api_lifecycle.py tests/test_api_chat.py -v`
Expected: FAIL，失败点落在新状态未接入上下文。

**Step 3: 写最小实现**

- 把最近一次自我编程结果纳入聊天系统上下文
- 确保 lifecycle / wake 不覆盖已有自我编程冷却与最近结果

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest -q && cd ../.. && cd apps/desktop && npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/tests/test_api_lifecycle.py services/core/tests/test_api_chat.py
git commit -m "feat: 打通自我编程结果与全链路上下文"
```
