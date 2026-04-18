# legacy-safe-cleanup simplification

日期：2026-04-18

## 1. 背景

- 这轮目标不是泛化做技术债清理，而是沿着当前前后端主链、配置读取、测试依赖和兼容边界，找出已经不再生效或只剩壳的 legacy 实现。
- 复杂度扫描显示仓库中 `orchestrator`、`history`、`self_programming` 等历史概念仍留下不少命名残留；但运行面和 API 映射也提示，不能只靠名字判断。
- 如果不区分“仍承担兼容职责”和“仓库内零消费者的空壳”，后续会继续在类型、事件名、helper 和测试心智上保留无效分叉。

## 2. 当前最小目标

- 保持当前默认主链稳定：`apps/desktop` 的 `overview/chat/tools` 主入口，`memory/persona` 次级入口，以及 `services/core` 的 chat/runtime/world/tools 主链。
- 只删除已经确认“仓库内零调用、零测试覆盖、运行时不会进入、并且已有主链替代”的 legacy 壳。
- 保留仍承担旧 hash、旧数据路径、旧快照反序列化兼容职责的边界。

## 3. 运行链路依据

- `scan_project_surface.py` 给出的主要信号是：先看默认导航与默认路由，再看不再服务 chat/runtime 的历史模块。
- `analyze_api_mapping.py` 结果显示，前端真实映射只覆盖 21 个后端接口；大量未映射接口不能直接视为 legacy，需要结合页面和运行链判断。
- `analyze_runtime_surface.py` 与 `analyze_ui_api_flow.py` 对当前仓库的前端 hash 路由抓取不足，因此本轮额外手工核对了 `App.tsx`、`useAppChrome.ts`、`AppMainContent.tsx`、`AppSidebar.tsx`、`main.py`、`runtime_ext/bootstrap.py` 和相关测试。
- 手工核对后确认：默认导航只暴露 `overview/chat/tools`，`memory/persona` 为次级入口，`#/history` 与 `#/orchestrator` 仅作为 legacy hash 兼容跳转保留。

## 4. 范围

### 4.1 保留

- `apps/desktop/src/lib/appRoutes.ts` 的 `normalizeLegacyHash()`。
证据：`useAppChrome.ts` 在初始化和 `hashchange` 时都会进入；`App.test.tsx` 有专门覆盖 `#/history` 和 `#/orchestrator`；已有明确替代方案是跳转到 `#/`，因此这是仍有兼容价值的边界，不应删除。
- `services/core/app/main.py` 中大部分依赖导出。
证据：`get_chat_gateway`、`get_goal_repository`、`get_memory_repository`、`get_memory_service`、`get_mempalace_adapter`、`get_morning_plan_draft_generator`、`get_state_store`、`get_world_repository`、`get_world_state_service` 仍被多个 API 测试通过 `app.main` 导入并用于 dependency override；这些兼容导出仍有真实消费者，不应整块删除。

### 4.2 延后

- `services/core/app/config.py` 对 `OPENAI_MODEL` 的 legacy 回退。
证据：仓库里仍有 README、`.env.local.example`、`enhanced_gateway.py` 和 `test_gateway.py` 在引用；名字旧，但仍在有效配置链里。

### 4.3 删除或冻结

- `services/core/app/config.py:get_mempalace_enabled()`。
证据：仓库内 `rg` 结果只有函数定义和历史文档提及，没有任何代码或测试调用；聊天记忆主链已经在注释和启动链中完全切到 MemPalace，没有额外兼容价值。
- `services/core/app/realtime.py` 中整组 orchestrator realtime 发布方法。
证据：仓库内没有任何调用点，前端也没有任何对应事件消费者，测试同样未覆盖；当前 realtime 主链只使用 `runtime/memory/persona/chat` 事件。
- `apps/desktop/src/lib/api.ts` 中整组前端 orchestrator 类型声明。
证据：这些类型在仓库内只有自引用，没有任何页面、hook、API client 或测试导入；当前桌面主链也不存在 orchestrator 页面入口或对应 API。
- `services/core/app/runtime_ext/snapshot.py` 中“只有 `mempalace_adapter`、没有 `chat_memory_runtime`”的中间消息 fallback。
证据：当前启动链 `runtime_ext/bootstrap.py` 和依赖注入 `api/deps.py` 都保证 chat 主链使用 `chat_memory_runtime`；仓库内没有任何只设置 `mempalace_adapter` 再走 snapshot 的消费者或测试。
- `services/core/app/llm/gateway.py` 对 `GatewayResponse` 与 `EnhancedChatGateway` 的兼容导出。
证据：仓库内真实消费者只剩测试导入；运行时代码直接使用 `ChatResult` 或从 `enhanced_gateway.py` 导入实现本体，没有主链调用价值。
- `services/core/app/domain/models.py` 与 `services/core/app/runtime.py` 中的 `orchestrator_session` 字段及整组 orchestrator 会话模型。
证据：仓库内已没有任何 API、UI、service、runtime 或测试消费者；唯一剩余用途是旧状态字段残留。当前仅保留对旧 `focus_mode="orchestrator"` 的归一化兼容。
- `services/core/app/runtime_ext/data_backup.py` 中的 `legacy_memory_jsonl` 备份项。
证据：前端与 API 只把备份视为 zip 路径，不依赖该 key 必须存在；仓库内没有任何测试、导入流程或运行逻辑要求 `.data/memory.jsonl` 继续出现在备份清单中。
- `services/core/app/main.py` 中 `get_chat_memory_runtime` 与 `get_morning_plan_planner` 的兼容导出。
证据：它们在运行时由各自路由直接从 `app.api.deps` 使用，但仓库内没有任何代码或测试再从 `app.main` 导入这两个名字；保留在 `app.main` 只会扩大一个已经部分 legacy 化的导出面。

## 5. 决策卡片与门禁

- `analyze_ui_api_flow.py` 本轮没有产出可用的 `decision_cards`、`safety_gates` 或 `execution_mode`，因为它没有识别出当前前端 hash 路由。
- 默认动作采用“人工补运行链证据，再做最小清理”，没有直接依据脚本结果删路由或删接口。
- 这轮按人工核对后的结论执行，等价于谨慎的 `eligible_for_safe_cleanup` 子集：只清零消费者壳，不改主入口、不删仍承担兼容职责的边界。

## 6. Guided Patch Workflow

- 本轮没有使用 route 级 guided patch plan。
- 原因是候选点不在某个顶层页面删除，而是分散在前端公共类型、后端 realtime 壳和配置 helper。
- 执行策略改为：先列候选与证据，再只落地零消费者壳。

## 7. 具体改动

- 删除 `apps/desktop/src/lib/api.ts` 中整组未被任何消费者使用的 orchestrator 类型定义，减少前端 API 类型表面的遗留概念。
- 删除 `services/core/app/realtime.py` 中未被任何调用点触达的 orchestrator realtime 发布方法，收敛 runtime 事件面。
- 删除 `services/core/app/config.py` 中零调用的 `get_mempalace_enabled()` helper，避免继续保留“已切主链但还留兼容壳”的误导。
- 删除 `services/core/app/runtime_ext/snapshot.py` 中 adapter-only 的中间 fallback，保留 `chat_memory_runtime -> memory_repository` 两层清晰链路。
- 删除 `services/core/app/llm/gateway.py` 中仅用于旧导入路径的 `GatewayResponse` / `EnhancedChatGateway` 兼容出口，并同步改测试导入。
- 删除 `services/core/app/domain/models.py` 中无消费者的 orchestrator 会话模型，以及 `BeingState.orchestrator_session` 字段。
- 删除 `services/core/app/runtime.py` 中对 `orchestrator_session` 的旧状态归一化逻辑，并补测试确认旧字段会被忽略。
- 删除 `FocusMode.ORCHESTRATOR` 枚举值，并在 `BeingState` 上保留旧字符串到 `autonomy` 的兼容归一化。
- 删除 `services/core/app/runtime_ext/data_backup.py` 中不再有消费者的 `legacy_memory_jsonl` 备份入口，备份默认只覆盖当前仍在使用的数据面。
- 删除 `services/core/app/main.py` 中零消费者的 `get_chat_memory_runtime` 与 `get_morning_plan_planner` 兼容导出，保留其余仍被测试 override 使用的导出。

## 8. 同步文档与测试

### 8.1 文档

- 新增本文件，记录候选清单、保留/删除/暂缓判断、验证结果与风险。

### 8.2 测试

- 前端通过：`npm test -- --run src/lib/api.test.ts`
- 前端通过：`npm test -- --run src/lib/api.test.ts src/App.test.tsx -t "redirects legacy history route to overview and keeps memory as secondary entry|redirects legacy orchestrator route to overview|renders capability hub when route is capabilities"`
- 后端未跑成：`python3 -m pytest tests/test_api_realtime.py tests/test_config_paths.py tests/test_api_deps.py tests/test_api_state.py`
原因：当前环境缺少 `pytest`。
- Python 语法检查通过：`python3 -m py_compile services/core/app/config.py services/core/app/realtime.py`
- Python 语法检查通过：`python3 -m py_compile services/core/app/runtime_ext/snapshot.py services/core/app/llm/gateway.py services/core/tests/test_morning_plan_planner.py services/core/tests/test_api_chat.py services/core/tests/test_enhanced_gateway.py`
- Python 语法检查通过：`python3 -m py_compile services/core/app/domain/models.py services/core/app/runtime.py services/core/tests/test_runtime.py`
- Python 语法检查通过：`python3 -m py_compile services/core/tests/test_domain_models.py`
- Python 语法检查通过：`python3 -m py_compile services/core/app/runtime_ext/data_backup.py`
- Python 语法检查通过：`python3 -m py_compile services/core/app/main.py`

### 8.3 关联检查

- 运行了 `python3 tools/skills/project-simplifier/scripts/check_related_artifacts.py`。
- 结果提示了大量历史文档与测试的“可能相关”引用，但没有发现需要与本轮删除点一起同步更新的当前代码消费者。
- 该脚本运行时还生成了 `services/core/.mempalace/...` 的本地数据变动，这些不是本轮 legacy 清理的一部分。

## 9. 影响文件

- `apps/desktop/src/lib/api.ts`
- `services/core/app/config.py`
- `services/core/app/realtime.py`
- `services/core/app/runtime_ext/snapshot.py`
- `services/core/app/llm/gateway.py`
- `services/core/app/domain/models.py`
- `services/core/app/runtime.py`
- `services/core/app/runtime_ext/data_backup.py`
- `services/core/app/main.py`
- `services/core/tests/test_domain_models.py`
- `services/core/tests/test_morning_plan_planner.py`
- `services/core/tests/test_api_chat.py`
- `services/core/tests/test_enhanced_gateway.py`
- `services/core/tests/test_runtime.py`
- `docs/plans/2026-04-18-legacy-safe-cleanup-simplification.md`

## 10. 验证方式

- 先用 `rg` 追踪调用点、测试覆盖和运行链。
- 再跑前端定向测试，确认 legacy hash 兼容与 capability 路由仍然可进入。
- 再跑 Python 语法检查，确保删壳后后端文件仍可编译。
- 额外运行 `python3 tools/check_file_budgets.py`，确认这轮没有把大文件压力继续做坏。
- 额外用 `rg` 复核 `GatewayResponse`、`EnhancedChatGateway` 和 snapshot 中间 fallback 是否已没有遗留消费者。

## 11. 风险与回退

- 已知风险 1：后端 pytest 无法在当前环境运行，因此缺少更完整的 API 回归证据。
- 已知风险 2：`npm test -- --run src/App.test.tsx src/lib/api.test.ts` 的全量组合执行会命中一个与本轮改动无关的既有失败：`updates a goal status from the app and refreshes the rendered goal` 断言文本重复。
- 已知风险 3：旧状态里的 `focus_mode="orchestrator"` 现在会被自动映射到 `autonomy`，如果未来真要恢复这个模式，需要重新引入显式语义而不是依赖旧字符串。
- 已知风险 4：旧时代产物 `.data/memory.jsonl` 不再被默认备份；如果未来发现仍有外部迁移流程依赖它，需要单独恢复为显式迁移工具，而不是继续混在默认备份面里。
- 回退路径很小：恢复上述文件中的删除块和测试导入即可，不涉及状态迁移、接口协议变更或数据结构改写。

## 12. 下一步

- 当前明确不做：删除 legacy hash 跳转、删除旧数据备份兼容入口。
