# 世界事件系统 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为数字人增加会被记忆、会被查看的世界事件。

**Architecture:** 在 `AutonomyLoop` 中根据当前 `WorldState` 定时生成 `kind="world"` 的记忆事件。`/world` 从记忆仓储读取最近一条世界事件，并与当前世界状态一起返回。前端轮询 `/world` 后显示最近事件。

**Tech Stack:** Python, FastAPI, React, pytest, vitest

---

### Task 1: 后端世界事件生成与读取

**Files:**
- Modify: `services/core/tests/test_world_service.py`
- Modify: `services/core/tests/test_autonomy_loop.py`
- Modify: `services/core/tests/test_api_world.py`
- Modify: `services/core/app/world/models.py`
- Modify: `services/core/app/world/service.py`
- Modify: `services/core/app/agent/loop.py`
- Modify: `services/core/app/main.py`

### Task 2: 前端显示最近世界事件

**Files:**
- Modify: `apps/desktop/src/App.test.tsx`
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/components/WorldPanel.tsx`
