# history-safe-cleanup simplification

日期：2026-04-17

## 1. 背景

- 桌面端已经在收敛默认导航，把能力中枢、记忆库、主控工作台等非主链路入口逐步降为次级入口；独立 `history` 顶层路由会继续增加信息架构成本。
- `history` 页面本身没有独立 API 链路，只是把 `HistoryPanel` 再包成一个单页详情壳层，属于低价值重复入口。
- 如果继续保留独立入口，README、hash 路由、测试与页面壳层都会继续承诺一条并不属于主导航主链的路径，后续收敛会越来越难。

## 2. 当前最小目标

- 保留“查看自我编程历史 + 查看单条详情 + 对已生效记录执行回滚”这条能力链。
- 去掉独立 `history` 顶层路由，让这条能力并回总览，避免默认入口继续膨胀。
- 兼容旧 `#/history` 链接，不留下死链。

## 3. 运行链路依据

- `analyze_runtime_surface.py` 显示当时前端共有 8 个顶层 route，`history` 属于 heavy frontend group，但没有体现为主链必需入口；脚本建议优先隐藏或移除 route，再决定是否删除实现。
- `generate_guided_patch_plan.py --route history` 给出的结果是：
  - `current_execution_mode=eligible_for_safe_cleanup`
  - `plan_status=guided_patch_plan_available`
  - `patch_direction=safe_cleanup`
  - `target_files` 只命中 `apps/desktop/src/pages/HistoryPage.tsx`
- `analyze_api_mapping.py` 没有发现 `history` 自身独占的前后端 API 风险；自我编程历史仍然走既有 `/self-programming/history` 与 `/self-programming/{id}/rollback`。
- `analyze_ui_api_flow.py` 在变更后显示 `overview` 仍有既存异常项：
  - `decomposeGoal -> /goals/{param}/decompose`
  - `fetchActiveTaskExecutions -> /goals/execution/active`
  - `fetchTaskExecutionStats -> /goals/execution/stats`
  这些异常项与本次 `history` 收敛无关，但意味着总览不是删除候选，所以本轮采取“迁移入口”而不是“继续砍总览能力”。

## 4. 范围

### 4.1 保留

- `HistoryPanel` 的数据加载与列表展示能力。
- 历史详情侧栏、健康度展示、文件列表与“回滚此操作”按钮。
- 旧 `#/history` 用户习惯，通过自动跳转落到新的总览位置。

### 4.2 延后

- 不处理 `overview` 里既存的 goals API 映射缺口；这属于下一轮“补后端路由或清理前端遗留调用”的范围。
- 不动后端 `self_programming_routes.py`；本轮只收敛前端入口，不删 API。
- 不继续收口工具箱中的 `HistoryTab`，因为那是工具执行记录，不是自我编程历史。

### 4.3 删除或冻结

- 删除独立页面文件 `apps/desktop/src/pages/HistoryPage.tsx`。
- 冻结 `#/history` 作为 legacy hash，仅用于跳转兼容，不再作为独立 route 存活。

## 5. 决策卡片与门禁

- 针对 `history` route 的 guided patch 结果没有额外 `decision_cards`，属于低风险清理项。
- 默认动作建议采用为：先移除独立 route 壳层，再同步更新导航承诺、测试和文档。
- `history` route 的门禁结论：
  - `deletion_readiness=reviewable`
  - `current_execution_mode=eligible_for_safe_cleanup`
  - 脚本仍提示 `guided_execution_possible=false`，因此本轮按照“人工确认后执行低风险清理”处理，而不是把脚本视为自动补丁。
- 变更后 `overview` route 的执行模式仍是 `decision_only`，原因是其余 goals 相关 API 缺口未解；这也是本轮没有进一步删总览能力的原因。

## 6. Guided Patch Workflow

- 输入：`python3 tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py --route history`
- 脚本建议的直接目标：
  - `apps/desktop/src/pages/HistoryPage.tsx`
- 人工扩展的同步目标：
  - `apps/desktop/src/App.tsx`
  - `apps/desktop/src/pages/OverviewPage.tsx`
  - `apps/desktop/src/App.test.tsx`
  - `README.md`
  - `docs/plans/2026-04-17-history-safe-cleanup-simplification.md`
- 最终采用方向：
  - 不再保留单独 page route
  - 把 page 壳层提炼为总览内的 `SelfProgrammingHistorySection`
  - 用 legacy hash 跳转保留兼容性

## 7. 具体改动

- 新增 `apps/desktop/src/components/SelfProgrammingHistorySection.tsx`，承接原 `HistoryPage` 的详情与回滚交互。
- `apps/desktop/src/pages/OverviewPage.tsx` 新增自我编程历史区块，让总览统一承载状态、历史和回滚。
- `apps/desktop/src/App.tsx` 移除 `history` route 定义与页面渲染逻辑；`#/history` 现在会自动归一到 `#/`。
- 删除 `apps/desktop/src/pages/HistoryPage.tsx`。

## 8. 同步文档与测试

### 8.1 文档

- 更新 `README.md`，把“历史记录”模块说明改成“总览中的自我编程历史”。
- 新增本说明文档，记录这次收敛的门禁证据、变更范围与遗留风险。

### 8.2 测试

- 更新 `apps/desktop/src/App.test.tsx`，新增 legacy `#/history` 跳转断言，确保旧入口不会失效。
- 复用现有 App 壳层测试，确认收敛后主界面仍可正常渲染。
- 本轮未新增后端测试，因为后端契约未改。

### 8.3 关联检查

- `check_related_artifacts.py` 已运行。
- 脚本列出若干历史文档为 review candidates，但没有发现新的、必须与本次 `history` 入口同步修改的测试或文档引用。
- 这轮已处理的直接用户可见承诺主要是 `README.md` 与 `App.test.tsx`。

## 9. 影响文件

- `apps/desktop/src/App.tsx`
- `apps/desktop/src/pages/OverviewPage.tsx`
- `apps/desktop/src/components/SelfProgrammingHistorySection.tsx`
- `apps/desktop/src/pages/HistoryPage.tsx`（删除）
- `apps/desktop/src/App.test.tsx`
- `README.md`
- `docs/plans/2026-04-17-history-safe-cleanup-simplification.md`

## 10. 验证方式

- `cd apps/desktop && npm test -- --run App.test.tsx`
- `python3 tools/skills/project-simplifier/scripts/analyze_api_mapping.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`
- `python3 tools/skills/project-simplifier/scripts/check_related_artifacts.py`

## 11. 风险与回退

- 当前已知风险：
  - 自我编程历史并入总览后，`OverviewPage` 的职责进一步增大；若后续继续加内容，需要再评估是否拆分为更明确的子区块。
  - `overview` 里既有 goals API 缺口仍在，和本轮无直接关系，但会影响后续更激进的总览收敛。
- 最小回退路径：
  - 恢复 `apps/desktop/src/pages/HistoryPage.tsx`
  - 在 `apps/desktop/src/App.tsx` 恢复 `history` route 与对应渲染分支
  - 从 `apps/desktop/src/pages/OverviewPage.tsx` 去掉 `SelfProgrammingHistorySection`

## 12. 下一步

- 下一轮还能继续做的减法：
  - 决定 `overview` 中 goals 相关异常调用是补 API 还是删前端遗留入口。
  - 如果总览持续膨胀，可把“自我编程历史”折叠成可展开区块，进一步降低首屏复杂度。
- 当前明确不做的内容：
  - 不删除自我编程历史 API。
  - 不调整工具执行历史的 `HistoryTab`。
  - 不处理主控、能力中枢、记忆库之外的更大导航重构。
