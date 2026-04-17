# orchestrator 默认路径残留收口

## 为什么这次要简化

当前默认产品路径已经不再把 orchestrator 作为主入口，但桌面端仍残留几处会误导默认使用路径的表述和前端暴露：

- 默认文案还会把用户引向“高自治能力 / 治理后台 / 复杂治理能力”。
- 旧的 `#/orchestrator` hash 入口没有显式折返主路径。
- 前端 `BeingState` 仍把 `orchestrator` 焦点模式和 `orchestrator_session` 作为默认状态契约的一部分。
- `App.test.tsx` 里还保留了 `/orchestrator/*` 的旧 mock，容易继续暗示主路径会访问这些接口。

这和“小晏是数字人主链优先、复杂能力降级为可选入口”的方向不一致，所以这轮只收默认路径暴露，不动后端可选 orchestrator 实现。

## 当前最小目标

- 保持默认主链继续聚焦 `overview / chat / tools` 与次级的 `memory / persona`
- 保留 orchestrator 作为代码层面的可选能力
- 去掉默认导航、默认路由、默认状态暴露和默认文案中的误导性残留

## 保留清单

- 后端 orchestrator 领域模型与可选实现保持不动
- 前端现有默认顶层路由：`overview`、`chat`、`persona`、`memory`、`tools`、`capabilities`
- 记忆库与人格设置仍保留为次级入口

## 延后清单

- 后端 `services/core/app/domain/models.py` 中的 `FocusMode.ORCHESTRATOR`
- 后端 `BeingState.orchestrator_session` 持久化与运行态字段
- `apps/desktop/src/lib/api.ts` 里未被使用的一整组 orchestrator 类型定义

这些项属于“可选能力仍在代码层保留”的范围，本轮不继续扩大改动半径。

## 删除或冻结了什么

- 冻结默认 UI 对 orchestrator 焦点模式和 session 字段的直接感知
- 删除 `App.test.tsx` 中不再被默认主路径访问的 `/orchestrator/sessions`、`/orchestrator/scheduler` mock
- 将遗留 `#/orchestrator` hash 入口显式重定向到总览页

## 决策卡片与门禁结论

- 问题定义：这是主路径收敛，不是能力扩张，也不是运行时重排。
- 影响边界：仅限 `apps/desktop` 默认导航、默认 hash 路由、前端状态契约和相关测试/文案。
- 本体优先结论：`allow_local_change`
- 主要风险：如果后端未来真的向默认 UI 下发 `focus_mode=orchestrator`，前端不应误显示为“休眠”。
- 执行模式：沿用 project-simplifier 的 `eligible_for_safe_cleanup`

本体优先判断：

- 主体性影响：减少“后台工作台”感，强化“她的状态与对话”而非治理台。
- 连续性影响：不改运行时主流程，不影响 wake/chat/world 主链。
- 记忆影响：无记忆结构变更。
- 意图与执行边界影响：仅收紧默认暴露，没有新增执行中心或权限。
- 安全与回退影响：旧入口只是重定向到总览，风险可回退。

## 运行面与整改计划

运行脚本结论：

- `scan_project_surface.py` 仍将 `orchestrator` 标为重域，但默认顶层路由中已无 orchestrator。
- `analyze_runtime_surface.py` 显示默认前端路由仅有 `overview/chat/persona/memory/tools/capabilities`。
- `analyze_ui_api_flow.py` 对默认路由未发现阻断异常；`overview`、`chat` 均为 `eligible_for_safe_cleanup`。
- `generate_guided_patch_plan.py --route overview`
  - `plan_status`: `guided_patch_plan_available`
  - `patch_direction`: `safe_cleanup`
- `generate_guided_patch_plan.py --route chat`
  - `plan_status`: `guided_patch_plan_available`
  - `patch_direction`: `safe_cleanup`

本轮实际采用的整改方向：

- 前端默认 hash 层显式把 `#/orchestrator` 归并回 `#/`
- 前端默认 `BeingState` 不再暴露 orchestrator 相关字段
- 默认页面文案改成“次级入口”，不再把复杂治理能力挂在主路径旁
- 测试中删掉默认路径不会再访问的 orchestrator mock，并补上 legacy hash 重定向覆盖

## 具体改动文件

- `apps/desktop/src/App.tsx`
- `apps/desktop/src/pages/OverviewPage.tsx`
- `apps/desktop/src/lib/api.ts`
- `apps/desktop/src/App.test.tsx`

## 同步删改了哪些文档和测试

- 测试：更新 `apps/desktop/src/App.test.tsx`
- 文档：新增本文件，记录本轮默认路径收敛结论

说明：`check_related_artifacts.py` 因仓库当前存在其他未提交改动，输出了大量非本轮变更的关联项；本轮仅对当前实际修改文件落盘说明，没有顺带改历史计划文档。

## 异常项与处置

- 异常项：`apps/desktop/src/lib/api.ts` 里仍保留整组 orchestrator 类型定义，但当前默认 UI 已无引用。
- 处置：接受为“可选能力仍保留”的显式延后项，不在本轮删除，避免顺手扩大改动半径。

## 文件体积、重复与性能

- 大文件情况：`apps/desktop/src/App.tsx` 仍为 1081 行，继续超预算，但本轮没有再向其中新增复杂逻辑，只增加了一个很小的 legacy hash 归一化分支；`apps/desktop/src/lib/api.ts` 仍为 1557 行，同样维持超预算但略有收缩。
- 重复情况：测试里关于 orchestrator mock 的重复样板被删除，重复保持下降。
- 性能敏感路径：仅增加一次 hash 归一化判断，不涉及热路径成本放大。

## 验证

- `python3 tools/check_file_budgets.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_runtime_surface.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`
- `npm test -- src/App.test.tsx`

实际结果：

- `App.test.tsx` 24 个测试全部通过。
- 运行面分析仍显示默认顶层路由里没有 orchestrator。
- 文件预算检查显示仓库里原有超大文件仍存在：`apps/desktop/src/App.tsx`、`apps/desktop/src/lib/api.ts`、`services/core/app/api/chat_routes.py`。

## 当前遗留风险和下一步

- 后端默认状态模型仍保留 `FocusMode.ORCHESTRATOR` 与 `orchestrator_session`，说明“可选能力仍在边缘代码里可见”，但已不再占据桌面端默认主路径。
- 如果下一轮继续收敛，可考虑把 `apps/desktop/src/lib/api.ts` 中未使用的 orchestrator 类型整体移到单独可选模块，进一步减轻默认前端契约面。
