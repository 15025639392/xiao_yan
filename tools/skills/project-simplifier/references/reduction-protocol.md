# Reduction Protocol

这个协议定义了这个 skill 在当前仓库里做减法时的最低执行标准。

## 1. 先证据，后删改

默认顺序：

1. 跑复杂度扫描
2. 跑运行面分析
3. 跑 API 映射分析
4. 跑 UI -> API -> Backend 三级流向分析
5. 定义最小目标
6. 处理三级流向分析里的异常项和删除阻断项
7. 列出保留 / 延后 / 删除候选
8. 再开始改代码

不要跳过前六步，直接按感觉删。

## 2. 删除候选的成立条件

一个模块至少满足下列两条，才适合进入删除候选：

- 不在默认前端路由或默认导航里
- 不在当前主链路 API 中
- 没有被当前前端 API client 明确映射到
- 只服务边缘能力或实验能力
- 增加依赖体积、启动复杂度或理解成本
- 可以先通过关闭入口或降级为可选能力来验证

## 3. 默认优先级

通常优先从这里开始做减法：

- 默认导航之外的页面和组件
- 运行主链路之外的后端模块
- 重型可选依赖对应的能力路径
- rollout、canary、watch、report、replay 类脚本
- 历史性强、但不参与当前交付的文档产物

## 4. 默认不直接动的内容

- 当前前端主入口
- 当前后端启动脚本
- chat/runtime 主路径
- 当前前端仍在调用的 API
- 还没有完成三级流向分析的顶层路由
- 被三级流向分析标记为 `blocked` 的路由、组件和相关 API
- 任何没有完成引用检查的核心 API

## 5. 异常项判定

如果 `scripts/analyze_ui_api_flow.py` 输出了异常项，至少要先归类，再决定是否删改。

当前默认归类：

- `decomposition_capability_without_api_route`：后端已经有目标分解能力，但当前没有对前端暴露对应 API 路由
- `execution_runtime_without_api_route`：后端已经有任务执行态/统计能力，但当前没有对前端暴露对应 API 路由
- `backend_logic_without_api_route`：后端同域路由和代码实现都存在，但当前前端契约没有匹配到 API 路由
- `unmapped_api_functions`：前端 API 调用没有映射到已知后端路由，默认视为高风险异常
- `frontend_contract_without_backend_route`：后端同域路由存在，但这条前端契约本身没有对应后端路由
- `backend_code_hint_without_route`：没有匹配到后端路由，但后端代码或测试里仍然有实现线索
- `likely_stale_frontend_api`：既没有匹配路由，也没有明显后端实现线索，更像遗留前端契约

默认处置：

- 先结合同域路由样本、后端代码提示和测试线索，确认它是遗留 UI 调用、后端待实现能力、API 路由漏暴露，还是映射规则缺口
- 如果已经被细分到 `decomposition_capability_without_api_route` 或 `execution_runtime_without_api_route`，默认优先按“能力存在但未暴露 API”处理，而不是先假设前端陈旧
- 如果脚本已经给出 `default_action` 或 `suggested_actions`，先把它当作默认收敛方向，再结合业务和主链路风险决定是否偏离
- 如果脚本已经给出 `decision_cards`、`safety_gates` 或 `execution_mode`，先看门禁，再决定是否进入代码改动阶段
- 在没有结论之前，不把对应路由列为“可直接删除”
- 如果业务上决定暂时接受风险，必须在文档里明确写出接受理由和后续处理人/方向

## 6. 执行模式

当前默认执行模式：

- `decision_only`：只允许输出结论、文档和下一步，不直接落代码
- `guided_backend_patch`：允许按决策卡片去补后端 API 路由，但仍要同步测试和文档
- `guided_frontend_patch`：允许按决策卡片去删减或隐藏前端入口，但仍要同步测试和文档
- `eligible_for_safe_cleanup`：当前没有阻断异常，可进入低风险收敛执行

最低要求：

- 只有在 `safety_gates` 没有关键失败项时，才允许从 `decision_only` 进入其他执行模式
- 如果有多个冲突的 `decision_cards`，默认退回 `decision_only`
- 即使进入可引导执行模式，也不能跳过文档、测试和关联检查

## 7. Guided Patch Plan

在 `analyze_ui_api_flow.py` 之后，默认继续运行 `scripts/generate_guided_patch_plan.py`。

这个脚本至少要回答四件事：

- 当前 route 的 `plan_status` 是 `plan_only` 还是 `guided_patch_plan_available`
- 当前更偏向补后端、删前端、低风险清理，还是继续观察
- 这轮最可能要动哪些前端/后端文件
- 哪些文档和测试属于“直接同步目标”，哪些只是“人工复核目标”

使用规则：

- 如果 `plan_status` 还是 `plan_only`，停在整改计划和文档，不直接自动落补丁
- 如果 `patch_direction` 已经明确，后续真实改动要优先围绕 `target_files` 展开，而不是重新凭感觉找入口
- `sync_targets.docs` 和 `sync_targets.tests` 里的内容默认要在同一轮改动里同步处理
- `doc_manual_review` 和 `test_manual_review` 不是必改清单，但必须过一遍并在文档里说明结论
- guided patch plan 只能生成计划，不能绕过门禁直接假装已经安全自动执行

## 8. 改动后的收尾

完成代码改动后，至少要做四件事：

1. 验证启动或测试命令
2. 同步删改受影响的文档
3. 同步删改受影响的测试
4. 生成并补全文档，说明遗留风险和下一步

如果这四件事没有完成，就不算一次完整的简化工作。

## 9. 文档与测试同步规则

当你删除或改动下面这些内容时，必须同步检查对应文档和测试：

- 页面、路由、导航入口
- API、请求体、响应体、配置项
- 启动命令、脚本、依赖、默认开关
- 任何会影响 README、`docs/plans/`、`docs/requirements/`、测试用例语义的改动

最低要求：

- 失效文档要么更新，要么删除，不允许继续描述旧行为
- 失效测试要么更新，要么删除，不允许保留“明知不成立”的断言
- 文档里的验证命令必须和当前实现一致
- 如果本轮碰到了异常项，文档必须记录异常项分类、处置结论和剩余风险
- 如果选择暂时保留某份旧文档，必须明确标注它不再代表当前默认实现
- 收尾前至少运行一次 `scripts/check_related_artifacts.py`，把脚本输出中的 review candidates 过一遍
