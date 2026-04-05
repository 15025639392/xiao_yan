# 对话失败续生成 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 当聊天流式输出因为 `502` 或上游中断失败时，允许用户在原 assistant 气泡上继续生成，而不是新建一条回复。

**Architecture:** 新增 `POST /chat/resume`，请求中显式带回原 user message、原 `assistant_message_id` 和已成功显示的 `partial_content`。后端沿用现有 `/ws/app` 的 `chat_*` 实时事件，把新输出继续发到同一个 assistant 气泡；前端为失败气泡提供“继续生成”动作并复用同一条消息状态。

**Tech Stack:** FastAPI, WebSocket, OpenAI Responses streaming, React, Vitest, Pytest

---

### Task 1: 后端 resume 协议

**Files:**
- Modify: `services/core/app/llm/schemas.py`
- Modify: `services/core/app/main.py`
- Test: `services/core/tests/test_api_chat.py`

**Step 1: 写失败测试**

- 断言 `POST /chat/resume` 返回原 `assistant_message_id`
- 断言 websocket 续生成事件继续发到原 assistant 气泡
- 断言 gateway 指令里包含“从 partial_content 继续且不要重复”

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py -q`
Expected: FAIL because `/chat/resume` does not exist and resume instruction is missing.

**Step 3: 写最小实现**

- 增加 resume 请求 schema
- 提取共用的 chat streaming 执行函数
- 为 resume 构造 continuation instruction，并复用原 `assistant_message_id`

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py -q`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/llm/schemas.py services/core/app/main.py services/core/tests/test_api_chat.py
git commit -m "feat: 支持对话失败后续生成"
```

### Task 2: 前端失败气泡续生成

**Files:**
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/components/ChatPanel.tsx`
- Modify: `apps/desktop/src/App.tsx`
- Test: `apps/desktop/src/App.test.tsx`

**Step 1: 写失败测试**

- 断言 `chat_failed` 后 assistant 气泡保留已输出文本并显示“继续生成”
- 断言点击“继续生成”会请求 `/chat/resume`
- 断言新的 `chat_delta` 继续拼接到原 assistant 气泡

**Step 2: 运行测试并确认失败**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx`
Expected: FAIL because failed bubble has no resume action and app does not call `/chat/resume`.

**Step 3: 写最小实现**

- 为 assistant message 记录 `requestMessage`
- 增加 `resumeChat()` API
- 在 failed assistant bubble 上渲染“继续生成”
- 点击后把同一气泡切回 `streaming` 并继续拼接内容

**Step 4: 运行测试并确认通过**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx`
Expected: PASS

**Step 5: 提交**

```bash
git add apps/desktop/src/lib/api.ts apps/desktop/src/components/ChatPanel.tsx apps/desktop/src/App.tsx apps/desktop/src/App.test.tsx
git commit -m "feat: 前端支持失败后继续生成"
```

### Task 3: 回归验证

**Files:**
- Modify: `services/core/tests/test_api_realtime.py`
- Modify: `services/core/tests/test_gateway.py`

**Step 1: 写/补回归测试**

- 断言 realtime chat 事件协议未被破坏
- 断言 gateway 仍可稳定处理 delta/completed 事件

**Step 2: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py services/core/tests/test_api_realtime.py services/core/tests/test_gateway.py -q`
Expected: PASS

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx src/lib/realtime.test.ts`
Expected: PASS

**Step 3: 提交**

```bash
git add services/core/tests/test_api_realtime.py services/core/tests/test_gateway.py
git commit -m "test: 覆盖对话续生成回归"
```
