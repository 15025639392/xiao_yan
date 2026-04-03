# 内在世界第一层 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为数字人增加最小可用的内在世界层，并让自主 thought 受其影响。

**Architecture:** 扩展 `WorldState` 和 `WorldStateService`，让其根据 `BeingState`、当前时间和焦点目标状态推导 `energy / mood / focus_tension`。随后在 `AutonomyLoop` 中读取该状态，改变 thought 的措辞。

**Tech Stack:** Python, FastAPI, pytest

---

### Task 1: 世界状态推导

**Files:**
- Modify: `services/core/tests/test_world_service.py`
- Modify: `services/core/app/world/models.py`
- Modify: `services/core/app/world/service.py`

**Step 1: 写失败测试**

- 睡眠时推导出 `low / tired / low`
- 白天有活跃目标时推导出高 tension 和 engaged mood
- 完成态焦点目标推导出 calm mood

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_world_service.py -v`
Expected: FAIL

**Step 3: 写最小实现**

- 扩展 `WorldState`
- 让服务支持根据时间、苏醒状态和目标状态推导内在世界

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_world_service.py -v`
Expected: PASS

### Task 2: 自主 thought 接入内在世界

**Files:**
- Modify: `services/core/tests/test_autonomy_loop.py`
- Modify: `services/core/app/agent/loop.py`

**Step 1: 写失败测试**

- 夜晚低能量时，goal focus thought 会带出疲惫感
- 完成态 thought 会带出 calm 收尾感

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: FAIL

**Step 3: 写最小实现**

- 在 `AutonomyLoop` 中引入 `WorldStateService`
- 根据世界状态调整 thought 文案

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_autonomy_loop.py -v`
Expected: PASS
