# 知识库建设实施交接单（T1 启动）

## 结论

- 评审决策已闭环，实施可从 T1 直接启动。
- T1 目标是固化知识条目模型与命名空间规范，为 T2-T5 提供稳定契约。
- 本交接单给出第一批实现边界、测试命令与交付定义，便于开发无歧义开工。

## 下一步（唯一）

- 在实现分支提交 T1 的模型与仓储变更，并通过 `test_memory_repository.py`。

## 产物路径

- `/Users/ldy/Desktop/map/ai/docs/requirements/2026-04-12-knowledge-base-implementation-handoff.md`

## 1) T1 目标范围

- 在 `MemoryEvent` 或配套模型中补充知识实体所需字段：`knowledge_type`、`source_ref`、`version_tag`、`visibility`。
- 在 `MemPalaceMemoryRepository` 中明确命名空间约束：`chat`、`autobio`、`inner`、`knowledge`。
- 保持与现有 `/memory/*` API 向后兼容，不破坏现有字段解析。

## 2) 非目标

- 不实现外部知识源接入器。
- 不实现检索权重调优逻辑。
- 不调整前端展示层。

## 3) 影响文件（建议）

- `services/core/app/memory/models.py`
- `services/core/app/memory/mempalace_repository.py`
- `services/core/tests/test_memory_repository.py`
- `services/core/tests/test_domain_models.py`

## 4) 验收标准

- 新增字段在不传值时有明确默认行为。
- 命名空间字段校验可拒绝非法值。
- 旧数据加载不报错。
- 测试命令通过：
  - `pytest -q services/core/tests/test_memory_repository.py`
  - `pytest -q services/core/tests/test_domain_models.py`

## 5) 风险提示

- 模型字段变更可能影响 `model_dump_json()` 输出结构。
- 命名空间校验过严会影响历史数据兼容。

## 6) 回滚策略

- 若 T1 引发兼容问题，回滚模型新增字段并保留仓储读路径兼容逻辑。
- 回滚后继续使用当前稳定命名空间策略，不阻塞聊天主链路。
