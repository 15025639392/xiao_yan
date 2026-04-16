# Simplification Change Doc Template

建议文件位置：`docs/plans/YYYY-MM-DD-主题-simplification.md`

---

# 标题

日期：YYYY-MM-DD

## 1. 背景

- 当前项目为什么需要做这轮简化
- 当前复杂度主要来自哪里
- 如果不做，会带来什么问题

## 2. 当前最小目标

- 这轮简化之后，项目最少要稳定保留什么能力

## 3. 运行链路依据

- 复杂度扫描给出的主要收敛信号是什么
- 运行面分析说明默认主链路覆盖了哪些页面、路由、接口
- 如果动到了页面、入口或顶层组件，三级流向分析说明它会触达哪些 API client 和后端路由
- 如果存在未映射 API 调用或删除阻断项，这轮分别属于什么异常类型，证据是什么，是否属于“能力存在但未暴露 API”，默认动作建议是什么，最后如何处理、接受或暂缓

## 4. 范围

### 4.1 保留

- 保留项 1
- 保留项 2

### 4.2 延后

- 延后项 1
- 延后项 2

### 4.3 删除或冻结

- 删除/冻结项 1
- 删除/冻结项 2

## 5. 具体改动

- 改动点 1
- 改动点 2

## 6. 决策卡片与门禁

- 这轮有哪些 `decision_cards`
- 默认动作建议是什么，最终是否采用
- `safety_gates` 哪些通过，哪些没通过
- 最终执行模式是 `decision_only`、`guided_backend_patch`、`guided_frontend_patch` 还是 `eligible_for_safe_cleanup`

## 7. Guided Patch Workflow

- `generate_guided_patch_plan.py` 输出的 `plan_status` 是什么
- 当前 `patch_direction` 是补后端、删前端、低风险清理还是继续观察
- `target_files` 指向了哪些前端/后端文件
- 哪些 `sync_targets.docs` / `sync_targets.tests` 属于直接同步目标
- 哪些 `doc_manual_review` / `test_manual_review` 只是人工复核目标，最后如何处理

## 8. 同步文档与测试

### 8.1 文档

- 更新/删除了哪些文档
- 哪些旧文档不再成立

### 8.2 测试

- 更新/删除了哪些测试
- 为什么这些测试需要跟着改

### 8.3 关联检查

- `scripts/check_related_artifacts.py` 发现了哪些相关文档/测试引用
- 哪些已经处理
- 哪些仍需人工确认

## 9. 影响文件

- `path/to/file1`
- `path/to/file2`

## 10. 验证方式

- `scripts/analyze_runtime_surface.py` 输出了什么关键信号
- `scripts/analyze_api_mapping.py` 输出了什么关键信号
- 如果本轮涉及页面/组件收敛，`scripts/analyze_ui_api_flow.py` 输出了什么关键信号
- 如果本轮生成了 guided patch plan，`scripts/generate_guided_patch_plan.py` 输出了什么 route、`plan_status`、`patch_direction` 和同步目标
- 如果 `scripts/analyze_api_mapping.py` 或 `scripts/analyze_ui_api_flow.py` 输出了异常类型、默认动作建议、`decision_cards`、`safety_gates`、`review_candidates` 或 `blocked` 路由，最后是如何闭环的
- 命令 1
- 命令 2

## 11. 风险与回退

- 当前已知风险
- 哪些异常项仍然被保留，以及为什么
- 如需回退，最小回退路径是什么

## 12. 下一步

- 下一轮还能继续做的减法
- 当前明确不做的内容
