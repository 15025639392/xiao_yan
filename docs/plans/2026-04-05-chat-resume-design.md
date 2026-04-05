# 对话失败续生成设计

## 目标

当 `POST /chat` 已经创建 assistant 气泡并开始流式输出后，如果上游响应中断或返回 `502 Bad Gateway`，前端允许用户点击“继续生成”，并把新内容续接到原来的 assistant 气泡中。

## 方案

- 保留 `POST /chat` 作为首次发送入口。
- 新增 `POST /chat/resume` 作为续生成入口。
- 续生成请求必须携带：
  - `message`：原始 user message
  - `assistant_message_id`：失败的 assistant 气泡 id
  - `partial_content`：已成功显示的 assistant 文本
- 后端继续复用现有 `/ws/app` chat 事件：
  - `chat_started`
  - `chat_delta`
  - `chat_completed`
  - `chat_failed`
- 续生成时沿用原 `assistant_message_id`，不新建 assistant 气泡。
- 模型提示中显式说明：从 `partial_content` 的结尾继续，不要重复已输出内容。

## 协议

### POST `/chat/resume`

请求：

```json
{
  "message": "昨天你说到一半停了",
  "assistant_message_id": "assistant_xxx",
  "partial_content": "我刚才想继续说的是，"
}
```

响应：

```json
{
  "response_id": "resp_resume_xxx",
  "assistant_message_id": "assistant_xxx"
}
```

### `/ws/app` chat 事件

续生成不新增事件类型，仍使用现有 `chat_started/chat_delta/chat_completed/chat_failed`。区别只有一点：

- `assistant_message_id` 必须等于原失败气泡 id。

## 数据流

1. 用户首次发送消息，前端创建 user message，并等待同 id 的 assistant 流式事件。
2. 如果后端或上游失败，前端将该 assistant 气泡标记为 `failed`，保留已输出内容。
3. 用户点击“继续生成”。
4. 前端调用 `POST /chat/resume`，提交原始 user message、原 assistant 气泡 id、当前 partial content。
5. 后端重新组装聊天上下文，并增加“从以下前缀继续、不要重复”的续写指令。
6. 后端继续通过 `/ws/app` 发送 chat 事件，事件中的 `assistant_message_id` 保持不变。
7. 前端收到新的 `chat_delta` 后继续拼接到原 assistant 气泡，收到 `chat_completed` 后清除失败态。

## 前端状态

- assistant message 需要额外保存：
  - `requestMessage`
  - `state`
- `state === "failed"` 时显示“继续生成”操作。
- 点击后仅将该气泡切回 `streaming`，不新增第二个 assistant 气泡。

## 后端实现边界

- 不兼容旧数据，也不为旧轮询逻辑保留分支。
- 如果 `assistant_message_id` 或 `partial_content` 缺失，直接按请求错误处理。
- 续生成只针对当前失败气泡，不做多分支会话恢复。

## 错误处理

- `/chat/resume` 再次失败时，继续发送 `chat_failed`，前端仍保留同一气泡并允许再次重试。
- 如果前端传入的 `partial_content` 与最终已落库消息不一致，以请求体为准继续生成，不额外做旧数据兼容。

## 验证

- 后端：
  - `POST /chat/resume` 返回原 `assistant_message_id`
  - websocket 续生成事件落在原气泡 id 上
  - gateway 收到包含“继续生成且不要重复”的指令
- 前端：
  - 失败气泡显示“继续生成”
  - 点击后复用原气泡继续打印
  - 完成后气泡恢复正常态
  - 再次失败时不丢失已生成内容
