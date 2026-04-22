# 小红书经营：REVIEWING 状态恢复协议

## 背景

当小红书经营工作域处于 `REVIEWING`（待确认发布）状态时，表示小晏已经通过浏览器器官把内容填到了小红书发布页，并停在了最后一步，等待用户在浏览器中手动确认并点击发布。

这个状态是 "review_before_publish" 发布模式的正常中间态，不是错误。

## 状态恢复流程

### 1. 用户侧动作

1. 在桌面端看到状态为「待确认发布」。
2. 切换到浏览器窗口，检查标题、正文、封面是否正确。
3. 确认无误后，在小红书发布页点击「发布」按钮。
4. 返回桌面端，点击「已手动发布，结束本轮」按钮。

### 2. 系统侧响应

前端发送 PATCH `/xhs-work-domain`：
```json
{ "status": "idle" }
```

后端收到从 `REVIEWING` → `IDLE` 的状态转换请求时，会执行以下动作：
- 将 `pending_drafts[0]` 消费到 `published_history`
- 清空 `pending_drafts` 和 `review_session_id`
- 减少 `backlog_count`
- 更新 `last_published_at`

### 3. 边界情况

- 如果用户不点击「已手动发布」，状态会一直保持 `REVIEWING`，直到下次前端轮询时用户主动操作。
- 如果用户直接 PATCH `status: idle` 但当前不是 `REVIEWING` 状态，系统不会消费草稿，只会简单切换状态。
- 浏览器会话在 REVIEWING 状态下保持打开；状态切到 IDLE 后，`review_session_id` 会被清空，浏览器页签可由用户自行关闭。

## 相关文件

- `services/core/app/api/runtime_routes.py` — PATCH `/xhs-work-domain` 端点实现
- `apps/desktop/src/pages/XiaohongshuPage.tsx` — 前端「已手动发布」按钮
- `services/core/tests/test_runtime_routes.py` — REVIEWING → IDLE 状态转换测试
