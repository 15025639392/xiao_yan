# Recommended `简化: <目标>` Targets

这份清单只服务于当前小晏仓库，目的是给出一组可以直接复制使用的“简化目标”。

使用方式：

- 直接把下面任一条发给 Codex。
- 如果你只想看判断，不想改代码，用 `简化分析:`。
- 如果你希望在门禁允许时直接落地，用 `简化执行:`。

---

## 当前优先级

### P0: 先处理但不要直接删

这些目标当前最值得先看，但重点不是直接删除，而是先把异常项或默认路径判断清楚。

- `简化: 处理 overview 路由的 goals 相关异常，判断是补后端 API 暴露还是前端降级`
- `简化分析: 针对 overview 路由生成整改计划，只输出 decision_cards 和 guided patch plan`
- `简化执行: 如果门禁允许，为 overview 路由补 goals 分解与执行态 API，并同步测试和文档`

原因：

- `overview` 是当前唯一被三级流向分析标记为 `blocked` 的路由。
- 它背后有 `decomposeGoal`、`fetchActiveTaskExecutions`、`fetchTaskExecutionStats` 三个未映射 API。
- 当前默认动作是“建议补后端路由”，不是“直接删前端入口”。

### P1: 最适合先做减法

这些目标对降低默认复杂度最划算，而且目前没有明显阻断异常。

- `简化: 收敛 orchestrator 页签，判断是否移出默认导航或降级为可选入口`
- `简化: 收敛 capabilities 页签，评估是否保留为默认可见入口`
- `简化: 收敛 history 页签，判断是否可以隐藏默认入口并同步清理测试文档`
- `简化: 清理 docs/requirements 和 docs/checkpoints 中已不代表当前默认实现的历史文档`

原因：

- `orchestrator`、`capabilities`、`history` 在当前运行面里更接近可选 UI，不是主链路核心。
- 历史需求文档会持续增加理解成本，但不直接提升默认闭环价值。
- `services/core/scripts` 现在只保留默认启动脚本，应继续避免把 rollout/canary/report/watch 类脚本放回该目录。
- 这些区域更适合先做“移出默认入口 / 冻结 / 文档清理”，风险通常比直接删主链路低。

### P2: 第二批适合收敛

这些目标可以做，但建议排在 P0/P1 之后。

- `简化: 评估 memory 页签是否应继续保留为默认主导航`
- `简化: 评估 tools 页签是否应收敛为更小的默认能力集合`
- `简化: 评估 persona 页签是否应降级为次级入口`
- `简化: 盘点 backend 中 self_programming、mcp、capabilities 域，找出不阻塞 chat/runtime 的模块`

原因：

- `memory`、`tools`、`persona` 当前都有明确的前后端映射，不属于“明显失效”的区域。
- 但它们仍然属于较重的能力组，适合在默认入口明确收缩后再继续做减法。

---

## 推荐直接复制的目标清单

### 默认入口类

- `简化: 收敛 orchestrator 页签`
- `简化: 收敛 capabilities 页签`
- `简化: 收敛 history 页签`
- `简化: 评估 memory 页签是否退出默认主导航`
- `简化: 评估 persona 页签是否退出默认主导航`

### 前后端契约类

- `简化: 处理 overview 路由的 goals API 异常`
- `简化分析: 判断 overview 路由更适合补后端 API 还是先保留观察`
- `简化执行: 为 overview 补 goals execution/decompose API，并同步删改文档测试`

### 后端模块类

- `简化: 盘点 services/core/app/orchestrator 是否可降级为可选能力`
- `简化: 盘点 services/core/app/self_programming 是否可移出默认路径`
- `简化: 盘点 services/core/app/memory 中重依赖路径，找出不阻塞主链路的部分`
- `简化: 盘点 services/core/app/capabilities 是否存在只服务边缘流程的 API`

### 脚本与文档类

- `简化: 保持 services/core/scripts 只承载默认启动脚本`
- `简化: 清理 docs/requirements 历史文档`
- `简化: 清理 docs/checkpoints 历史文档`
- `简化: 让 skill 相关文档与当前默认实现保持一致`

---

## 当前不推荐直接作为删除目标

- `简化执行: 直接删除 chat 主链路`
- `简化执行: 直接删除 overview 路由`
- `简化执行: 直接删除当前前端仍在调用的 runtime/config API`
- `简化执行: 直接删除默认启动脚本`

原因：

- `chat/runtime` 仍然是当前默认主链路。
- `overview` 还存在阻断异常，当前不适合直接进入删除路径。
- 默认入口、默认 API 和默认启动脚本都属于高风险区域，必须先过运行面和流向分析。

---

## 推荐使用顺序

1. 先用下面三条之一开局：
   - `简化: 收敛 orchestrator 页签`
   - `简化: 收敛 capabilities 页签`
   - `简化: 处理 overview 路由的 goals API 异常`
2. 如果目标是减默认复杂度，优先做“移出默认入口”而不是“直接删实现”。
3. 如果目标涉及 API 或 goals runtime，先停在 `简化分析:`，看完 guided patch plan 再决定是否 `简化执行:`。
4. 每次真正删改代码时，同步处理对应文档和测试。

---

## 这份清单基于哪些事实

- 当前前端顶层路由有 `overview`、`chat`、`persona`、`memory`、`history`、`tools`、`capabilities`、`orchestrator`
- 当前较重的前端组主要集中在 `orchestrator`、`memory`、`persona`、`tools`、`history`
- 当前较重的后端域主要集中在 `orchestrator`、`self_programming`、`memory`、`mcp`、`capabilities`
- 当前唯一 route 级阻断异常集中在 `overview`
- 当前默认主链路仍然优先围绕 `apps/desktop + services/core + chat/runtime`
