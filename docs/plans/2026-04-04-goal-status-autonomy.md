# 目标状态影响自主行为 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让数字人在自主循环中根据目标状态做出不同反应。

**Architecture:** 在 `AutonomyLoop` 中读取目标仓储的真实状态，并在每次 tick 时清理或处理非活跃目标。`completed` 目标产出一次完成式 thought，`paused` 与 `abandoned` 不再驱动自主推进。

**Tech Stack:** FastAPI, Python, pytest

---

### Task 1: 自主循环状态感知

**Files:**
- Modify: `services/core/tests/test_autonomy_loop.py`
- Modify: `services/core/app/agent/loop.py`

**Step 1: 写失败测试**

为以下行为补测试：

- `paused` 目标不会更新为推进式 thought
- `completed` 目标第一次生成完成式 thought，第二次不重复
- `abandoned` 目标不会生成完成式 thought

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: FAIL，失败点落在新增状态感知行为缺失。

**Step 3: 写最小实现**

- 在 `AutonomyLoop.tick_once` 中读取目标仓储状态
- 清理 `state.active_goal_ids` 中非 `active` 目标
- 为 `completed` 增加一次性收尾 thought

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/tests/test_autonomy_loop.py services/core/app/agent/loop.py docs/plans/2026-04-04-goal-status-autonomy-design.md docs/plans/2026-04-04-goal-status-autonomy.md
git commit -m "feat: 让目标状态影响自主行为"
```
