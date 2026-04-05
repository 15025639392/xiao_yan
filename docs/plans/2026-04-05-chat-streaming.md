# 对话流式输出 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将桌面对话改成通过现有 WebSocket 实时输出 assistant 文本增量，形成打印机效果。

**Architecture:** 保留 `POST /chat` 负责提交消息与返回确认，后端消费 OpenAI Responses streaming 并通过 `/ws/app` 广播 `chat_*` 事件。前端基于 `assistant_message_id` 维护一条增量中的 assistant 草稿消息，并在完成后与最终 runtime/memory 更新去重。

**Tech Stack:** FastAPI, WebSocket, httpx streaming, React, Vitest

---

### Task 1: 后端聊天协议

**Files:**
- Modify: `services/core/app/llm/schemas.py`
- Modify: `services/core/app/realtime.py`
- Modify: `services/core/app/main.py`
- Test: `services/core/tests/test_api_chat.py`
- Test: `services/core/tests/test_api_realtime.py`

**Step 1: 写失败测试**

- 断言 `POST /chat` 返回提交确认而不是 `output_text`
- 断言 websocket 会收到 `chat_started/chat_delta/chat_completed`

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py services/core/tests/test_api_realtime.py -q`

**Step 3: 写最小实现**

- 引入新的 chat 事件 payload
- 给 realtime hub 增加 `publish_chat_*`
- 修改 `/chat` 为提交确认 + 流式广播

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py services/core/tests/test_api_realtime.py -q`

**Step 5: 提交**

```bash
git add services/core/app/llm/schemas.py services/core/app/realtime.py services/core/app/main.py services/core/tests/test_api_chat.py services/core/tests/test_api_realtime.py
git commit -m "feat: 接入对话流式实时事件"
```

### Task 2: OpenAI streaming 桥接

**Files:**
- Modify: `services/core/app/llm/gateway.py`
- Test: `services/core/tests/test_gateway.py`

**Step 1: 写失败测试**

- 断言 gateway 可消费 Responses streaming 事件并产出完整文本与 delta

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_gateway.py -q`

**Step 3: 写最小实现**

- 增加 streaming 方法
- 解析 `response.created` `response.output_text.delta` `response.completed` `error`

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_gateway.py -q`

**Step 5: 提交**

```bash
git add services/core/app/llm/gateway.py services/core/tests/test_gateway.py
git commit -m "feat: 桥接 OpenAI Responses 流式输出"
```

### Task 3: 前端打印机效果

**Files:**
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/App.tsx`
- Test: `apps/desktop/src/App.test.tsx`
- Test: `apps/desktop/src/lib/realtime.test.ts`

**Step 1: 写失败测试**

- 断言发送后 assistant 草稿会随 `chat_delta` 增长
- 断言 `chat_completed` 后内容稳定
- 断言 `chat_failed` 时展示错误

**Step 2: 运行测试并确认失败**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx src/lib/realtime.test.ts`

**Step 3: 写最小实现**

- 更新 chat 提交返回类型
- 扩展 realtime 事件 union
- `App` 中按 `assistant_message_id` 维护增量消息

**Step 4: 运行测试并确认通过**

Run: `cd apps/desktop && npm test -- --run src/App.test.tsx src/lib/realtime.test.ts`

**Step 5: 提交**

```bash
git add apps/desktop/src/lib/api.ts apps/desktop/src/lib/realtime.ts apps/desktop/src/App.tsx apps/desktop/src/App.test.tsx apps/desktop/src/lib/realtime.test.ts
git commit -m "feat: 前端支持对话实时打印机效果"
```
