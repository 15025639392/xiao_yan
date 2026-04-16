# project-simplifier hardening

日期：2026-04-17

## 1. 背景

- 当前 `project-simplifier` skill 已能提供方向性建议，但自动化不足，更像检查清单，而不是能稳定支撑多轮项目收敛的执行工具。
- 主要短板最初是缺少真实运行面分析，无法快速回答“哪些前端路由和后端接口属于默认主链路”，同时缺少改动后的文档初稿生成能力。
- 在补上运行面分析之后，下一层明显缺口变成了“前端 API client 到后端路由”的映射证据不够，仍然不利于判断 API 是否可以删减。
- 再往下看，仅有 API 映射还不够，因为删页面、删顶层组件时仍然缺少“页面/组件 -> API client -> 后端路由”的三级流向证据，不利于评估一个路由背后的真实影响面。
- 补上三级流向之后，又暴露出一个收敛问题：脚本虽然能指出未映射 API，但如果它只是普通输出而不是明确异常项，做减法时仍然可能被忽略。
- 即使把异常项显式化之后，仍然还有一个缺口：如果不继续细分异常类型，执行者还是很难快速区分“遗留前端契约”和“后端逻辑已存在但 API 没暴露”。
- 在把异常类型继续拆开后，又能进一步看到另一层问题：同样是“后端逻辑存在但 API 没暴露”，分解能力和执行态能力的处置方式并不完全一样，最好继续给出更接近整改动作的判断。
- 即使类型已经足够细，如果最后不给默认动作，执行者还是容易停在分析结论，不知道这轮更应该补 API、删前端，还是继续观察。
- 即使有了默认动作，如果不继续明确“哪些情况下只能出决策、哪些情况下才允许进入引导执行”，skill 仍然容易在执行边界上摇摆。
- 即使有了执行边界，如果不继续把 route 级判断翻译成“这轮优先改哪些文件、哪些测试和文档必须一起动”的整改计划，执行者还是得手工把决策卡片再翻译一遍，容易走偏。
- 另外，仍然缺一个“改完代码后能不能快速发现残留文档/测试引用”的收尾检查能力，否则还是容易留下旧说明和旧测试。
- 如果不补齐这十一块，后续每次用这个 skill 做减法仍然会高度依赖人工判断，容易出现删改依据不足、前后端错位、异常项被忽略、异常类型误判、处置动作失焦、执行边界模糊、整改入口不清和收尾文档漏写的问题。

## 2. 当前最小目标

- 让 `project-simplifier` 至少具备十二项稳定能力：扫描项目复杂度、分析默认运行面、分析前端 API 到后端路由的映射关系、分析页面/组件到 API 与后端路由的三级流向、识别未映射 API 等异常项并阻断删除判断、细分异常类型并给出证据、把“能力未暴露 API”类问题继续拆到更接近整改动作的层级、产出默认动作建议、产出决策卡片/门禁/执行模式、生成 guided patch workflow、检查文档/测试残留引用、在完成代码改动后生成简化文档初稿。

## 3. 范围

### 3.1 保留

- 保留现有 skill 的主目标：围绕 `apps/desktop + services/core + chat/runtime` 收敛项目主链路。
- 保留原有检查清单与复杂度扫描思路。
- 保留“改完代码必须补文档”的强约束。

### 3.2 延后

- 暂不实现更深层的静态引用图分析，例如跨文件函数级引用追踪。
- 暂不做组件级、函数级的完整语义调用图；当前先补到“顶层路由/根组件 -> 可达文件 -> API client -> 后端路由”这一层。
- 暂不做自动异常修复；当前只负责把异常项结构化输出并纳入删除阻断条件。
- 暂不做语义级异常归因；当前异常细分仍是基于路径、同域路由、后端代码与测试线索的结构化证据。
- 暂不直接生成 API 补齐补丁；当前只把异常类型尽量细分到能指导后续整改，并进一步落成 guided patch 计划。
- 暂不自动执行默认动作；当前只负责把动作建议和整改计划显式写出来，真正落地仍由人决定。
- 暂不自动跨越执行门禁；当前只负责显式给出 `decision_only`、`guided_backend_patch`、`guided_frontend_patch` 和 `eligible_for_safe_cleanup`，并在 `decision_only` 时停在计划层。
- 暂不自动回填文档中的验证结果与风险说明，先生成结构化初稿。
- 暂不做语义级“文档内容是否仍然准确”的自动判断，guided patch plan 和关联检查先停留在路径、名称和结构证据层。

### 3.3 删除或冻结

- 冻结“只靠口头总结收尾”的旧工作方式。
- 删除运行面分析中的类型导入噪音，避免把 `type` 导入误判成页面能力。

## 4. 具体改动

- 强化 `tools/skills/project-simplifier/SKILL.md`，把默认工作流升级为“复杂度扫描 -> 运行面分析 -> API 映射 -> UI/API/Backend 三级流向分析 -> 收敛决策 -> 代码改动 -> 文档生成”的完整闭环。
- 新增 `tools/skills/project-simplifier/references/reduction-protocol.md`，把减法执行顺序、删除候选成立条件和收尾要求写成明确协议。
- 新增 `tools/skills/project-simplifier/scripts/analyze_runtime_surface.py`，输出前端默认路由、页面导入、后端 API 路由样本和重模块信号。
- 新增 `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`，输出前端 API client 函数与后端路由的映射关系。
- 升级 `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`，把未匹配前端 API 细分为异常类型，并补充同域路由样本、后端代码提示和建议动作。
- 再次升级 `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`，把“后端逻辑存在但没有 API 路由”继续细分为 `decomposition_capability_without_api_route` 和 `execution_runtime_without_api_route`，让异常项更接近真实整改方向。
- 再次升级 `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`，为每类异常补充 `default_action`、优先级与动作摘要，让分析结果直接带出默认整改方向。
- 再次升级 `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`，为每个未匹配调用补充 `decision_card`，把默认方向进一步收敛成“建议补后端路由 / 建议删前端入口 / 建议保留观察 / 建议先调查再改”。
- 新增 `tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`，输出每个顶层路由对应的根组件、可达文件样本、API client 函数以及后端路由，用来判断删页面或删入口时的真实波及面。
- 升级 `tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`，复用 API 映射脚本的异常细分结果，把未映射 API 等情况结构化为 `anomalies`、`suggested_actions`、`decision_cards`、`safety_gates`、`review_candidates` 与 `deletion_readiness`，让异常项直接参与删改判断。
- 新增 `tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py`，把 route 级异常、决策卡片和执行模式翻译成结构化整改计划，明确当前是 `plan_only` 还是 `guided_patch_plan_available`、建议补后端还是删前端、优先改哪些文件，以及哪些文档和测试要直接同步、哪些只做人工复核。
- 新增 `tools/skills/project-simplifier/scripts/check_related_artifacts.py`，输出当前改动可能波及但尚未同步处理的文档和测试引用。
- 升级 `tools/skills/project-simplifier/scripts/check_related_artifacts.py`，把 `tools/skills/` 纳入搜索范围，并把 skill 内部 Markdown 与 `tests/` 目录也纳入文档/测试分类，避免 skill 自己的脚本、协议和模板脱节。
- 新增 `tools/skills/project-simplifier/scripts/generate_change_doc.py`，自动生成 `docs/plans/YYYY-MM-DD-主题-simplification.md` 初稿。
- 升级 `tools/skills/project-simplifier/scripts/scan_project_surface.py`，过滤 `__pycache__`、`.git`、`node_modules` 等噪音目录，并补充 `plan_docs` 统计。
- 升级 `tools/skills/project-simplifier/SKILL.md`、`references/reduction-protocol.md` 和 `references/change-doc-template.md`，把“先生成 guided patch plan 再动文件”“文档/测试必须同步删改”“删路由前先看三级流向分析”“异常项必须先处置或写清接受理由”“先看决策卡片/门禁再决定是否执行”和“收尾前必须跑关联检查”纳入默认执行链路与强约束。

## 5. 影响文件

- `tools/skills/project-simplifier/SKILL.md`
- `tools/skills/project-simplifier/references/reduction-protocol.md`
- `tools/skills/project-simplifier/references/change-doc-template.md`
- `tools/skills/project-simplifier/scripts/scan_project_surface.py`
- `tools/skills/project-simplifier/scripts/analyze_runtime_surface.py`
- `tools/skills/project-simplifier/scripts/analyze_api_mapping.py`
- `tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`
- `tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py`
- `tools/skills/project-simplifier/scripts/check_related_artifacts.py`
- `tools/skills/project-simplifier/scripts/generate_change_doc.py`

## 6. 验证方式

- `python3 tools/skills/project-simplifier/scripts/scan_project_surface.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_runtime_surface.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_api_mapping.py`
- `python3 tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py`
- `python3 tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py --route overview`
- `python3 tools/skills/project-simplifier/scripts/check_related_artifacts.py`
- `python3 tools/skills/project-simplifier/scripts/generate_change_doc.py --slug skill-hardening --title 'project-simplifier hardening' --changed-file tools/skills/project-simplifier/SKILL.md --changed-file tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py --changed-file tools/skills/project-simplifier/scripts/check_related_artifacts.py --changed-file tools/skills/project-simplifier/scripts/generate_change_doc.py`
- 确认生成文档路径：`docs/plans/2026-04-17-skill-hardening-simplification.md`
- API 映射分析当前结果：`58` 个前端 API 函数成功映射到后端路由，`3` 个前端调用未匹配，`64` 个后端路由未被前端 API client 直接使用。
- API 映射异常细分当前结果：`3` 个未匹配前端调用已继续拆分为 `1` 个 `decomposition_capability_without_api_route` 和 `2` 个 `execution_runtime_without_api_route`。
- 默认动作建议当前结果：这 `3` 个未匹配前端调用目前都指向 `consider_adding_backend_api_route`，说明当前默认方向更偏向“先补后端 API 暴露能力”，而不是直接删前端入口。
- 决策卡片当前结果：这 `3` 个未匹配前端调用都生成了“建议补后端路由”方向的决策卡片。
- 三级流向分析当前结果：`8` 个顶层路由中，`5` 个路由存在 API 使用，`1` 个路由存在异常项并被标记为 `blocked`；当前唯一 review candidate 是 `overview`，其 `decomposeGoal` 属于 `decomposition_capability_without_api_route`，`fetchActiveTaskExecutions` 与 `fetchTaskExecutionStats` 属于 `execution_runtime_without_api_route`，并且 route 级 `suggested_actions` 也指向先评估补 API。
- 执行门禁当前结果：`overview` 已经生成 `decision_cards` 和 `suggested_actions`，但因为 `blocking_anomalies_resolved` 仍未通过，当前执行模式保持 `decision_only`；没有异常的路由则可进入 `eligible_for_safe_cleanup`。
- guided patch plan 当前结果：`overview` 会被翻译成 `plan_only + backend_api_exposure` 的整改计划，明确当前还不能自动落补丁，但下一步方向已经收敛到后端 API 暴露；脚本会直接给出前端契约文件、前端调用点、后端路由文件、后端逻辑文件，以及 docs/tests 的“直接同步目标”和“人工复核目标”。
- 测试环境当前结果：`services/core/pyproject.toml` 已声明 `pytest`，但当前 shell 的 `python3` 环境没有安装 `pytest`，因此这轮没有跑通新增脚本的单测，只做了脚本级验证。
- 关联检查当前结果：skill 自身的 `SKILL.md`、协议模板和硬化文档已经被纳入搜索面；当前 `check_related_artifacts.py` 也会提醒这类 skill 内部文档是否需要跟着更新。

## 7. 风险与回退

- 当前运行面分析、API 映射分析和三级流向分析仍然是结构级信号，不是完整的语义调用图；在做真正删除决策时，仍需要结合人工判断。
- 当前未匹配的前端调用 `decomposeGoal`、`fetchTaskExecutionStats`、`fetchActiveTaskExecutions` 更像真实的前后端脱节，需要后续单独确认是遗留调用还是待实现能力。
- 三级流向分析当前从 `App.tsx` 顶层路由和本地 import 图出发，尚未覆盖动态 import、运行时拼接路径或组件内部的更深层行为分支，因此它适合做删改前的快速圈定，不适合单独作为最终删除依据。
- 当前异常项分类还比较克制，只把未映射 API 直接作为高风险阻断项；后续如果要覆盖更多异常类型，需要避免把正常的多对一映射误判成风险。
- 当前异常细分依然基于 token 和结构线索，证据质量比“只有未映射列表”更高，但仍不能替代真实接口验证。
- 当前“能力未暴露 API”细分已经能区分分解能力与执行态能力，但还不能自动判断究竟应该补 API 还是删前端入口。
- 当前默认动作建议已经能给出方向，但本质上仍是启发式输出，不应替代产品和主链路判断。
- 当前执行模式和门禁已经能表达“能不能进入引导执行”，但仍不能替代真正的改动前验证；特别是只要阻断异常未消失，就必须停在 `decision_only`。
- 当前 guided patch plan 虽然已经把决策卡片翻译成了更明确的整改入口，但本质上仍然是高质量执行计划，不会直接生成真实补丁。
- 当前关联检查和 guided patch plan 里的同步目标仍然主要基于路径名、文件名和结构线索，不会理解完整语义，因此仍然可能漏掉“内容已经过时但未显式引用路径”的情况。
- 文档生成器目前只生成初稿，不会自动填入真实验证结果与结论，因此提交前仍需人工补全。
- 如需回退，最小路径是删除新增脚本与协议文件，并将 `tools/skills/project-simplifier/SKILL.md` 回退到强化前版本。

## 8. 下一步

- 下一轮可以继续强化到“页面内关键组件/面板 -> API client -> 后端路由”的更细粒度视角，而不止是顶层路由。
- 也可以继续补“异常项类型扩展”，例如把当前的结构化证据继续拆成“遗留 UI、后端未实现、API 路由漏暴露、映射规则缺口”，或者把动作建议继续做成“建议补 API / 建议删前端 / 建议保留观察”的更明确决策卡片。
- 也可以继续把 guided patch workflow 从“生成整改计划”推进到“在用户明确授权时生成真实 patch 草案”。
- 也可以继续强化到“改动文件 -> 文档章节 -> 测试用例”的更细粒度检查。
- 也可以继续加强文档生成器，让它自动接入 `git diff --name-only` 或测试结果摘要。
- 当前明确不做的是全仓库级静态程序分析和自动删除执行，这一步仍保留人为判断。
