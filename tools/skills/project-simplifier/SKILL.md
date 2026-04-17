---
name: project-simplifier
description: 用于简化复杂、过度设计或难以推进的软件项目。适合收敛范围、定义最小可运行版本、识别可删除模块、制定低风险瘦身步骤。用户也可以直接用“简化: <目标>”“简化分析: <目标>”“简化执行: <目标>”来触发。当前仓库优先使用它来收敛小晏的前后端主链路。
---

# Project Simplifier

在用户要求“简化项目”“收敛范围”“做减法”“先做最小版本”“删掉不必要模块”时使用本 skill。
也接受以下短触发写法：

- `简化: <目标>`
- `简化分析: <目标>`
- `简化执行: <目标>`
- `简化只出方案: <目标>`

核心目标不是产出空泛建议，而是把项目收敛到一个可解释、可运行、可继续迭代的最小闭环。

## 触发约定

- `简化: <目标>`：默认先分析，必要时继续落地。
- `简化分析: <目标>`：只做判断、证据、门禁结论和整改计划。
- `简化执行: <目标>`：在门禁允许时直接进入代码改动，并同步文档和测试。
- `简化只出方案: <目标>`：停在 `decision_cards`、`guided patch plan` 和文档建议，不直接改代码。
- 如果用户没有额外限定，默认把 `简化:` 解释为优先使用当前 skill 的标准工作流，而不是只给口头建议。

## 默认工作流

1. 先确认当前版本的最小用户价值。
2. 运行 `scripts/scan_project_surface.py`，获得项目规模、重模块与优先收敛信号。
3. 运行 `scripts/analyze_runtime_surface.py`，确认前端路由、页面与后端 API 的真实运行面。
4. 运行 `scripts/analyze_api_mapping.py`，确认前端 API client 函数和后端路由的实际映射关系。
5. 运行 `scripts/analyze_ui_api_flow.py`，确认每个顶层路由背后会触达哪些页面/组件、API client 和后端路由，并查看脚本给出的异常项与删除阻断信号。
6. 对未映射 API、异常路由和删除阻断项先做判定：至少看清它属于哪类异常，并结合同域路由与后端代码提示，确认是遗留 UI、待实现能力、分解能力未暴露 API、执行态能力未暴露 API、已存在后端逻辑但缺 API 暴露，还是映射规则缺口。
7. 读取脚本给出的默认动作建议，明确这轮更偏向“补 API”“删前端入口”“先调查再决定”中的哪一种。
8. 读取 `decision_cards`、`safety_gates` 和 `execution_mode`，明确这轮是只出决策，还是已经进入可引导执行状态。
9. 运行 `scripts/generate_guided_patch_plan.py`，把 route 级判断翻译成结构化整改计划，至少看清当前是 `plan_only` 还是 `guided_patch_plan_available`，以及建议改哪些前端/后端文件、哪些文档和测试要在同一轮同步处理。
10. 识别必须保留的运行链路、页面、接口和脚本。
11. 标出可延后、可冻结、可删除的模块。
12. 给出按风险排序的瘦身步骤。
13. 如果用户要求落地，且 `execution_mode` 已经进入 `guided_backend_patch`、`guided_frontend_patch` 或 `eligible_for_safe_cleanup`，就以 guided patch plan 为编辑底稿开始改代码、脚本或配置；否则先停在决策、整改计划与文档阶段。
14. 如果删除或改动了功能、入口、模块、接口或数据结构，同步删改对应文档和测试，避免残留误导信息。
15. 运行 `scripts/check_related_artifacts.py`，检查还有哪些文档和测试引用可能需要同步处理。
16. 代码改动完成后，运行 `scripts/generate_change_doc.py` 生成文档初稿，再补全验证、异常项处置、整改计划执行结果与风险说明。

## 输出要求

- 必须产出 `当前最小目标`
- 必须产出 `保留清单`
- 必须产出 `延后清单`
- 必须产出 `删除候选`
- 必须产出 `实施顺序`
- 只要脚本发现异常项，必须产出 `异常项与处置`
- 如果脚本给出了默认动作建议，必须产出 `默认动作与理由`
- 如果脚本给出了 `decision_cards`、`safety_gates` 或 `execution_mode`，必须产出 `决策卡片与门禁结论`
- 如果运行了 `scripts/generate_guided_patch_plan.py`，必须产出 `整改计划`
- 如果发生了代码改动，必须产出 `文档产物`

先下结论，再给依据。避免“可以考虑”“也许可以”这种弱结论。

## 小晏项目的默认收敛原则

- 优先保留“一条能跑通的主链路”。
- 当前默认主链路是：`apps/desktop` + `services/core` + 基础 chat/runtime。
- 人格、记忆、工具、自主调度、自我编程等能力，如果没有直接阻塞主链路，应优先降级而不是继续扩展。
- 文档、实验脚本、观测脚本、canary、回放与演进流水线，默认属于二级资产，除非用户明确要求保留。
- 如果某模块增加了理解成本、启动成本、依赖体积或失败面，但不提升当前最小价值，优先建议冻结或移出默认路径。

## 执行前优先检查

- 哪个命令能把项目跑起来。
- 前后端真正使用了哪些页面、接口、状态和依赖。
- 是否存在只在文档里重要、但不在运行链路上的模块。
- 是否存在只为边缘功能服务的重型依赖。
- 是否存在多个概念层重复表达同一能力。

## 仓库专属资源

- 小晏项目专属检查清单：`references/xiao-yan-checklist.md`
- 小晏项目推荐简化目标清单：`references/recommended-simplify-targets.md`
- 收敛执行协议：`references/reduction-protocol.md`
- 改动完成后的文档模板：`references/change-doc-template.md`
- 复杂度扫描脚本：`scripts/scan_project_surface.py`
- 运行面分析脚本：`scripts/analyze_runtime_surface.py`
- API 映射分析脚本：`scripts/analyze_api_mapping.py`
- UI -> API -> Backend 三级流向分析脚本：`scripts/analyze_ui_api_flow.py`
- 文档/测试关联检查脚本：`scripts/check_related_artifacts.py`
- 引导整改计划脚本：`scripts/generate_guided_patch_plan.py`
- 文档初稿生成脚本：`scripts/generate_change_doc.py`

先读本文件，再按需读取检查清单与执行协议。
如果要快速得到一个“哪里最适合做减法”的事实列表，先运行复杂度扫描，再运行运行面分析和 API 映射分析。

## 强约束

- 不能只凭主观感觉决定删除候选，至少要结合运行面分析结果。
- 不能删除前端仍在调用的后端 API，除非 API 映射分析已经证明该调用已迁移或失效。
- 不能删除一个顶层路由或页面，除非三级流向分析已经说明它背后的 API 和后端影响范围可接受。
- 如果三级流向分析将某个路由标记为 `blocked` 或存在 `unmapped_api_functions`，不能把它直接列为可删除候选，除非文档中明确记录了异常项结论与处置。
- 如果 API 映射分析已经把未匹配调用细分为异常类型，结论里必须引用这些类型和证据，不要只写“有 3 个未映射 API”。
- 如果脚本已经给出默认动作建议，结论里必须明确采用、拒绝或推迟该建议，而不是停在“需要人工确认”。
- 如果 `execution_mode` 仍是 `decision_only`，不能假装这轮已经进入安全自动执行阶段。
- 如果已经生成 guided patch plan，真正改代码前必须先看 `target_files`、`sync_targets` 和 `plan_status`，不能跳过这层直接凭感觉动文件。
- 不能在没有验证主链路的情况下删除默认入口、页面或 API。
- 如果删除或改动了代码，对应文档和测试必须同步删改，不能留下失效说明、失效验收命令或失效测试。
- 在结束前，至少跑一次关联检查，确认没有明显残留的文档或测试引用。
- 不能只给口头建议；如果发生代码改动，必须落盘文档。
- 如果扫描结果和人工判断冲突，先把冲突写进文档，再决定是否继续删改。

## 推荐命令顺序

```bash
python3 tools/skills/project-simplifier/scripts/scan_project_surface.py
python3 tools/skills/project-simplifier/scripts/analyze_runtime_surface.py
python3 tools/skills/project-simplifier/scripts/analyze_api_mapping.py
python3 tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py
python3 tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py --route <route>
python3 tools/skills/project-simplifier/scripts/check_related_artifacts.py
python3 tools/skills/project-simplifier/scripts/generate_change_doc.py --slug <topic>
```

## 改动完成后的文档要求

只要这个 skill 导致了代码、配置、默认入口、依赖或模块边界的变更，就必须生成或更新一份 Markdown 文档。

### 默认落点

- 默认写入 `docs/plans/`
- 推荐命名：`YYYY-MM-DD-主题-simplification.md`
- 一次收敛对应一份文档，不要把多轮不同主题混在同一文件里

### 文档至少要包含

- 为什么这次要简化
- 当前最小目标是什么
- 保留了什么
- 延后了什么
- 删除或冻结了什么
- 具体改了哪些文件
- 同步删改了哪些文档和测试
- 三级流向分析暴露了哪些异常项，最后如何处置
- 输出了哪些 `decision_cards`、`safety_gates` 和最终 `execution_mode`
- guided patch plan 输出了哪些 `target_files`、`sync_targets`、`plan_status` 和最终采用的整改方向
- 关联检查脚本发现了什么，还剩哪些人工确认项
- 用什么命令验证
- 当前遗留风险和下一步

### 何时使用更完整模板

- 如果改动跨前后端、多模块，或者影响默认主链路、架构边界、核心能力开关
- 这类情况优先遵循 `docs/plans/design-template.md` 与 `docs/plans/design-template-usage.md`

### 最低标准

- 不能只在最终回答里口头总结，必须有落盘文档
- 文档内容必须能让后来的人看懂这次为什么这么删、删了什么、还剩什么风险
- 如果脚本标出异常项，文档必须说明这些异常项是已解决、已接受还是显式延后
- 如果运行了 guided patch plan，文档必须说明哪些是“直接同步目标”，哪些只是“人工复核目标”，以及最终实际处理了哪些
- 文档初稿生成后，必须补上真实验证命令与实际改动文件
- 如果文档或测试需要跟着调整，这一步必须在同一轮改动里完成，不能留给“之后再清”
