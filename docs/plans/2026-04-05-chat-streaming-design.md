# 对话流式输出设计

## 目标

将桌面对话从“等待完整回复后一次性落屏”改为“提交后通过现有 `/ws/app` 实时推送增量文本”，形成打印机式输出。

## 方案

- 保留 `POST /chat` 作为发送入口。
- `POST /chat` 不再返回完整 `output_text`，只返回一次提交确认，包含 `response_id` 与 `assistant_message_id`。
- 现有 `/ws/app` 扩展四类事件：
  - `chat_started`
  - `chat_delta`
  - `chat_completed`
  - `chat_failed`
- 后端调用 OpenAI Responses API 的 streaming 能力，消费 `response.output_text.delta` 并桥接到 `chat_delta`。
- 对话最终落库仍在完整回复结束后统一执行，避免增量 token 进入记忆层。

## 协议

### POST `/chat`

请求：

```json
{ "message": "你好" }
```

响应：

```json
{
  "response_id": "resp_xxx",
  "assistant_message_id": "assistant_xxx"
}
```

### `/ws/app` 新增事件

- `chat_started`

```json
{
  "type": "chat_started",
  "payload": {
    "assistant_message_id": "assistant_xxx",
    "response_id": "resp_xxx"
  }
}
```

- `chat_delta`

```json
{
  "type": "chat_delta",
  "payload": {
    "assistant_message_id": "assistant_xxx",
    "delta": "你好"
  }
}
```

- `chat_completed`

```json
{
  "type": "chat_completed",
  "payload": {
    "assistant_message_id": "assistant_xxx",
    "response_id": "resp_xxx",
    "content": "你好，我在。"
  }
}
```

- `chat_failed`

```json
{
  "type": "chat_failed",
  "payload": {
    "assistant_message_id": "assistant_xxx",
    "error": "..."
  }
}
```

## 数据流

1. 前端提交用户消息到 `POST /chat`，本地立即插入 user message。
2. 后端立即生成 `assistant_message_id`，通过 hub 发送 `chat_started`。
3. 后端消费上游 streaming 事件，将文本增量桥接为 `chat_delta`。
4. 前端按 `assistant_message_id` 持续拼接 assistant 内容。
5. 后端收到完成事件后发送 `chat_completed`，再统一抽取记忆并落库。
6. 后续 `runtime_updated/memory_updated` 到来时，前端通过 message merge 去重，不重复插入最终 assistant 内容。

## 不兼容点

- 前端 `chat()` API 返回值变更，不再包含 `output_text`。
- 旧的一次性完整回复渲染逻辑删除，不保留兼容分支。

## 错误处理

- 上游流式失败时，后端发送 `chat_failed`，前端将对应 assistant 草稿标记为失败提示。
- 未收到 `chat_started` 前如果 HTTP 直接失败，前端沿用现有请求错误提示。

## 验证

- 后端：`/chat` 提交确认、WebSocket 收到 `chat_started/chat_delta/chat_completed/chat_failed`、记忆最终只落完整消息。
- 前端：发送后出现空 assistant 草稿、收到 delta 时逐字增长、完成后稳定展示、失败时显示错误。
