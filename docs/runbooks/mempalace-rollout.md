# MemPalace Rollout Runbook (小晏 Core)

## 1. 目标

- 在不改用户侧交互的前提下，将 `/chat` 的记忆检索与会话历史统一切到 `MemPalace`。
- 记忆系统已统一到 `MemPalace`，`/chat` 与记忆面板共用同一底层存储。

## 2. 配置项

在 `services/core/.env.local` 中：

- `MEMPALACE_PALACE_PATH`：MemPalace 数据目录
- `MEMPALACE_RESULTS_LIMIT`：每次注入 prompt 的最大命中条数（建议 `3`）
- `MEMPALACE_WING`：写入 wing（默认 `wing_xiaoyan`）
- `MEMPALACE_ROOM`：写入 room（默认 `chat_exchange`）

说明：当前版本聊天链路已强制启用 MemPalace，`MEMPALACE_ENABLED` 不再作为开关。

## 3. 依赖安装

在 `services/core` 执行：

```bash
pip install -e .
```

如果需要单独装：

```bash
pip install "mempalace>=3.1.0"
```

## 4. 初始化 MemPalace（首次）

```bash
mempalace init /path/to/seed-data
mempalace mine /path/to/seed-data --mode convos
```

说明：可以先导入历史会话导出，再让小晏在线持续镜像新对话。

## 5. 灰度步骤

1. 启动服务，确认可读写 palace。
2. 使用 10~20 条真实问答做回归：
   - 观察 `/chat` 是否 200
   - 观察回答是否出现长期记忆线索
   - 观察是否有异常日志（search/record）
3. 如异常率可接受，扩大流量；否则回滚。

## 6. 验证清单

```bash
pytest -q services/core/tests/test_mempalace_adapter.py
pytest -q services/core/tests/test_api_chat.py -k "mempalace"
pytest -q services/core/tests/test_autonomy_loop.py services/core/tests/test_prompt_builder.py
```

通过标准：全部通过，且 `/chat` 功能无回归。

## 7. 回滚方案

- 立即回滚：
  - 回滚到切换前版本（Git 回退）
  - 重启 `services/core`
- 当前版本不再支持通过环境变量切回旧聊天记忆链路。

## 8. 观测建议

- `/chat` P95 延迟增量（目标 < 120ms）
- MemPalace search/record warning 次数
- Prompt 长度变化（避免长期检索片段过长）

## 9. 风险与处理

- MemPalace/Chroma 未安装：适配器会降级，不应影响主链路。
- Palace 路径不存在：search 为空，record 失败并告警。
- 数据膨胀：可通过 `MEMPALACE_RESULTS_LIMIT` 和外部归档策略控制。
