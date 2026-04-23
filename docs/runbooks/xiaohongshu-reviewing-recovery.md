# 小红书经营：REVIEWING 状态恢复协议

## 背景

当小红书经营工作域处于 `REVIEWING`（待确认发布）状态时，表示小晏已经通过浏览器器官把内容填到了小红书发布页，并停在了最后一步，等待用户在浏览器中手动确认并点击发布。

这个状态是 "review_before_publish" 发布模式的正常中间态，不是错误。

## 状态恢复流程

### 1. 用户侧动作

1. 在桌面端看到状态为「待确认发布」。
2. 切换到浏览器窗口，检查标题、正文、封面是否正确。
3. 确认无误后，在小红书发布页点击「发布」按钮。

### 2. 系统侧响应

桌面端不再提供「已手动发布，结束本轮」收尾按钮。

当前实现下，`REVIEWING` 主要承担“发布页已填好、等待浏览器侧人工确认”的提示职责。

如果前端或系统后续将状态切回非 `REVIEWING`，后端只会：
- 清空 `review_session_id`
- 结束当前 review 会话

后端不会再因为 `REVIEWING` → `IDLE` 这一状态切换，自动消费草稿或写入 `published_history`。

### 3. 边界情况

- 如果用户已经在浏览器完成发布，桌面端当前不会再通过单独按钮回写“本轮已结束”。
- 如果用户直接 PATCH `status: idle`，系统不会消费草稿，只会简单切换状态。
- 浏览器会话在 REVIEWING 状态下保持打开；状态切到 IDLE 后，`review_session_id` 会被清空，浏览器页签可由用户自行关闭。

### 4. 排障记录：正文排版全部挤在一起

- 真实故障现象不是单纯“换行没生效”，而是小红书发布页正文里出现了字面量 `<p></p>`，最终导致内容挤成一块。
- 这次确认过的真实根因是：`apps/desktop/scripts/browser_driver.py` 已修复，但实际活跃的 `browser_driver` daemon 仍在跑旧版本脚本，所以真实发布链路没有吃到新逻辑。
- 这类问题的正确排障顺序是：
  1. 先看真实 Chrome 发布页，不要只看单元测试。
  2. 直接确认正文编辑器里是否出现字面量 `<p></p>`。
  3. 再确认 `/tmp/xiyan_browser_driver.sock` 对应 daemon 是否已切到新代码版本。
  4. 最后才判断是正文输入策略问题，还是 daemon 版本漂移。
- 正确恢复动作是：重启对应 `browser_driver` daemon，刷新或重新打开发布页，再重新触发一次正文填充。已经被旧逻辑写坏的当前页面内容不会自动恢复。
- 后续默认做法：凡是浏览器自动填充相关 bug，都先做“真实页面 + 活跃 daemon”双确认。
- 这次修复后，`browser_driver` 已增加代码版本校验；修改 `browser_driver.py`、`browser_driver_scripts.py`、`browser_driver_result_parser.py` 后，应由 `ensure_daemon` 主动淘汰旧 daemon。

## 相关文件

- `services/core/app/api/runtime_routes.py` — PATCH `/xhs-work-domain` 端点实现
- `apps/desktop/src/pages/XiaohongshuPage.tsx` — 前端 REVIEWING 提示区
- `services/core/tests/test_runtime_routes.py` — REVIEWING 状态清理测试
- `apps/desktop/scripts/browser_driver.py` — 浏览器发布页正文填充与 daemon 版本校验
