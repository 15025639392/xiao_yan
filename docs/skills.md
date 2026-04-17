# xiao_yan Skill 首页清单

本文档用于说明当前仓库内 7 个项目专用 skill 的用途、触发方式、适用问题和推荐顺序。

目标不是“把所有 skill 都用一遍”，而是让 AI 和人类都能更快选到当前最合适的那一个，减少跑偏、误改和无效重构。

## 总原则

- 先选最贴近当前问题的 skill，不要叠太多。
- 优先用能缩小问题边界的 skill，再用执行类 skill。
- 如果问题涉及数字人本体、权限边界、记忆、主流程，优先走架构评审，再决定是否编码。
- 如果问题只是局部 bug、局部改动或收尾同步，不要把它升级成大范围治理。

## 触发方式

当前 skill 推荐优先用以下方式触发：

- 直接在消息里点名：`$skill-name`
- 明确写出意图：例如“用 `core-change-entrypoint` 看一下这个改动入口”
- 对 `project-simplifier`，也可以用它已有的短触发：
  - `简化: <目标>`
  - `简化分析: <目标>`
  - `简化执行: <目标>`
  - `简化只出方案: <目标>`

推荐优先显式点名 skill，而不是只写模糊需求。这样更稳定，也更容易复现。

## 快速选择

如果你不确定该用哪个，可以先按下面的顺序判断：

1. 涉及数字人本体、主流程、长期状态、权限边界：
   使用 [`xiao-yan-architecture-guardian`](../tools/skills/xiao-yan-architecture-guardian/SKILL.md)
2. 只是要改后端或主链路，但还没找清入口和依赖链：
   使用 [`core-change-entrypoint`](../tools/skills/core-change-entrypoint/SKILL.md)
3. 问题是“运行起来不对了”“状态不对”“链路异常”：
   使用 [`runtime-bug-triage`](../tools/skills/runtime-bug-triage/SKILL.md)
4. 想做减法、收敛范围、删模块、压缩主链路：
   使用 [`project-simplifier`](../tools/skills/project-simplifier/SKILL.md)
5. 目标文件已经很大、很热、很混杂：
   使用 [`large-file-split-advisor`](../tools/skills/large-file-split-advisor/SKILL.md)
6. 涉及 `mempalace`、`chromadb`、`pypdf` 等可选依赖：
   使用 [`optional-dependency-boundary-check`](../tools/skills/optional-dependency-boundary-check/SKILL.md)
7. 改完了，担心文档、测试、验证命令没同步：
   使用 [`docs-and-tests-sync-guard`](../tools/skills/docs-and-tests-sync-guard/SKILL.md)

## Skill 清单

### 1. `xiao-yan-architecture-guardian`

- 作用：评审是否影响“小晏”作为数字人的主体性、连续性、记忆、意图与边界。
- 什么时候用：
  - 改 `memory / goals / orchestrator / self_programming / persona / tools / safety`
  - 改运行时主流程、长期状态、权限边界、自动化主链
  - 新增 worker、queue、event bus、后台执行机制
- 适合解决什么问题：
  - 这次改动会不会让产品更像工具，而不是数字人
  - 这次改动是否已经属于重要架构决策
  - 这轮应该直接改代码，还是先出设计结论
- 推荐触发：
  - `$xiao-yan-architecture-guardian`
  - “先用 `xiao-yan-architecture-guardian` 评审这个方案”
- 推荐顺序：
  - 当问题涉及本体、架构、主流程时，优先级最高，通常排在第一步

### 2. `core-change-entrypoint`

- 作用：在改后端或主链路前，先找清入口、依赖链、测试覆盖和最小落点。
- 什么时候用：
  - 改 `services/core`
  - 改 API 路由、service、repository、gateway、状态模型
  - 明确知道要改，但还不确定具体该动哪个文件
- 适合解决什么问题：
  - 入口到底在哪
  - 真实依赖链经过哪些模块
  - 这轮应该局部改，还是先提 helper / module
- 推荐触发：
  - `$core-change-entrypoint`
  - “先用 `core-change-entrypoint` 找这条链路的入口”
- 推荐顺序：
  - 对大多数后端改动，通常放在架构评审之后、实际编码之前

### 3. `runtime-bug-triage`

- 作用：按证据排查运行时问题，先复现、再缩小层级、再决定最小修复面。
- 什么时候用：
  - chat 行为异常
  - persona / world / goals / memory / tools 状态不对
  - API 返回和前端展示不一致
  - 链路“能跑但不对”
- 适合解决什么问题：
  - 根因到底在哪一层
  - 是生成逻辑、状态映射、降级路径还是权限边界的问题
  - 这次 bug 修复应该补哪一类测试
- 推荐触发：
  - `$runtime-bug-triage`
  - “用 `runtime-bug-triage` 先定位这个异常”
- 推荐顺序：
  - 用在 bug 排查最前面
  - 定位后，常接 `core-change-entrypoint` 或 `docs-and-tests-sync-guard`

### 4. `project-simplifier`

- 作用：围绕主链路做减法，收敛范围、定义最小闭环、找删除候选和安全执行顺序。
- 什么时候用：
  - 要简化项目
  - 要判断哪些模块该保留、延后、冻结或删除
  - 要围绕 `apps/desktop + services/core + chat/runtime` 收敛主链路
- 适合解决什么问题：
  - 当前最小用户价值是什么
  - 哪些模块不在主运行面上
  - 这轮减法应该先删什么、后删什么
- 推荐触发：
  - `$project-simplifier`
  - `简化: <目标>`
  - `简化分析: <目标>`
  - `简化执行: <目标>`
- 推荐顺序：
  - 用在做减法、收敛范围、治理复杂度时
  - 常与 `xiao-yan-architecture-guardian` 配合使用

### 5. `large-file-split-advisor`

- 作用：给超预算文件、长函数和混合职责模块提供最小拆分方案。
- 什么时候用：
  - 文件已经明显过大
  - 函数过长且混合职责
  - 这轮新增逻辑会继续恶化热点文件
- 适合解决什么问题：
  - 这次到底该不该拆
  - 是提 helper、提 module，还是先别动
  - 最小可回退拆分切口是什么
- 推荐触发：
  - `$large-file-split-advisor`
  - “先用 `large-file-split-advisor` 看这轮该怎么拆”
- 推荐顺序：
  - 通常在 `core-change-entrypoint` 之后
  - 当目标文件已超预算时，优先级会明显上升

### 6. `optional-dependency-boundary-check`

- 作用：检查可选依赖是否扩散进核心路径，以及降级行为是否仍然成立。
- 什么时候用：
  - 改 `mempalace`、`chromadb`、`pypdf`
  - 改 adapter、repository、gateway、依赖声明、启动逻辑
  - 改缺失依赖时的 fallback 或错误提示
- 适合解决什么问题：
  - 可选依赖有没有偷偷变硬依赖
  - import 和实例化位置是否越界
  - 没装依赖时系统还能不能清晰降级
- 推荐触发：
  - `$optional-dependency-boundary-check`
  - “先用 `optional-dependency-boundary-check` 看边界有没有失守”
- 推荐顺序：
  - 涉及可选依赖时，通常放在 `core-change-entrypoint` 之前或紧接之后

### 7. `docs-and-tests-sync-guard`

- 作用：确保代码改动后，文档、测试、runbook、验证命令和说明没有掉队。
- 什么时候用：
  - 改依赖、配置、启动方式、模块职责、降级行为、API、状态结构、skill
  - 做完 bug 修复或重构后准备收尾
- 适合解决什么问题：
  - 哪些文档要同步更新
  - 哪些测试该补或该改
  - 这轮实际验证命令应该怎么写
- 推荐触发：
  - `$docs-and-tests-sync-guard`
  - “最后用 `docs-and-tests-sync-guard` 过一遍同步项”
- 推荐顺序：
  - 大多数改动的最后一步

## 推荐组合

### 方案评审型

适合改主流程、长期状态、权限边界：

1. `xiao-yan-architecture-guardian`
2. `core-change-entrypoint`
3. 必要时 `optional-dependency-boundary-check`
4. 编码
5. `docs-and-tests-sync-guard`

### Bug 排查型

适合“现在不对，但还不清楚哪层坏了”：

1. `runtime-bug-triage`
2. `core-change-entrypoint`
3. 必要时 `large-file-split-advisor`
4. 编码
5. `docs-and-tests-sync-guard`

### 收敛减法型

适合清理复杂度、收缩主链路：

1. `project-simplifier`
2. 必要时 `xiao-yan-architecture-guardian`
3. 必要时 `large-file-split-advisor`
4. 编码或冻结
5. `docs-and-tests-sync-guard`

### 边界治理型

适合可选依赖、降级路径、适配层治理：

1. `optional-dependency-boundary-check`
2. `core-change-entrypoint`
3. 必要时 `xiao-yan-architecture-guardian`
4. 编码
5. `docs-and-tests-sync-guard`

## 使用建议

- 一个问题优先选 1 到 2 个 skill，除非确实跨多个决策面。
- 如果已经知道是架构问题，就不要从 bug triage 开始。
- 如果已经知道只是收尾同步，就不要再走入口定位。
- 如果文件已经超预算，不要等改完再想拆分。
- 如果涉及可选依赖，不要跳过边界检查，哪怕功能看起来已经跑通。

## 提示词 Demo

下面这些 demo 尽量结合当前仓库的真实模块、文件和问题类型来写，可以直接复制后再改一两处细节。

### 单 skill Demo

`xiao-yan-architecture-guardian`

```text
先用 $xiao-yan-architecture-guardian 评审一下：我想调整 goals 和 world event 的主流程，让小晏在没有 active goal 时更主动地创建新目标。先判断这会不会削弱数字人本体、意图优先或边界感，再告诉我这轮应该直接改代码还是先出设计结论。
```

```text
用 $xiao-yan-architecture-guardian 看一下，把 self_programming 的一些执行步骤进一步自动化，会不会让产品更像工具平台而不是数字人。请结合当前 services/core/app/self_programming 和主运行时流程给出结论。
```

`core-change-entrypoint`

```text
先用 $core-change-entrypoint 帮我定位 goal admission 这条链路。我要改“无 active goal 时创建候选目标”的行为，请找出真实入口、经过的 service / repository、相关状态文件和现有测试，不要直接开始改。
```

```text
用 $core-change-entrypoint 看一下 persona 页面配置保存失败这条链路，帮我从桌面端入口一直定位到 services/core 的 API 和 service 层，并判断最小安全改动点在哪里。
```

`runtime-bug-triage`

```text
先用 $runtime-bug-triage 排查一个问题：桌面端有时会显示 active goal，但服务端 admission 实际已经 defer 了。请结合 goals admission stats、前端状态映射和 API 返回链路，先拿证据再判断最小修复面。
```

```text
用 $runtime-bug-triage 看一下 memory 相关异常：有些对话事件似乎没被 mempalace 正常召回，但服务本身还能启动。先判断是写入、读取、降级路径还是前端展示问题。
```

`project-simplifier`

```text
简化分析: 围绕 apps/desktop + services/core + chat/runtime 收敛主链路，评估当前 tools、self_programming、memory 扩展能力里哪些应该先冻结，哪些必须保留。请输出保留清单、延后清单、删除候选和实施顺序。
```

```text
用 $project-simplifier 分析一下当前目标管理相关功能，看看 goal admission、history、canary、回放工具里哪些是主链必需，哪些是二级资产，目标是降低接手复杂度但不破坏小晏的数字人主线。
```

`large-file-split-advisor`

```text
先用 $large-file-split-advisor 看一下 apps/desktop/src/App.tsx 这轮还适不适合继续加逻辑。如果我要继续改 persona、goals 和 tools 导航相关状态，应该不拆、提 helper，还是先拆容器层？
```

```text
用 $large-file-split-advisor 评估 services/core/app/api/chat_routes.py。这个文件已经很大了，如果我要补一段和 chat skill 注入相关的逻辑，最小安全拆分方案应该是什么？
```

`optional-dependency-boundary-check`

```text
先用 $optional-dependency-boundary-check 看一下 mempalace 相关实现有没有越界。请重点检查 import、实例化、fallback 和启动路径，确认 services/core 在缺少 mempalace 时是否仍然能清晰降级。
```

```text
用 $optional-dependency-boundary-check 评估一下 chromadb 或 pypdf 如果后面重新接回来，会不会污染核心路径。请按 repository / adapter / domain / service 的边界给出风险判断。
```

`docs-and-tests-sync-guard`

```text
最后用 $docs-and-tests-sync-guard 过一遍：我刚改了 goals admission 的行为和相关 API，请告诉我 docs、runbook、tests、验证命令里哪些要同步更新，哪些可以保持不动。
```

```text
用 $docs-and-tests-sync-guard 检查这轮 skill 体系改动还缺哪些同步项，尤其是 docs/、tools/skills/、测试说明和文件预算检查命令。
```

### 组合 Demo

#### 1. 先评审，再定位，再改

适合主流程、状态模型、权限边界类问题：

```text
先用 $xiao-yan-architecture-guardian 判断这次 goals 主流程调整是否会影响小晏的主体性和意图优先；如果允许继续，再用 $core-change-entrypoint 找出真实入口、依赖链和最小改动点，最后再开始实现。
```

#### 2. 先排障，再决定要不要拆

适合大文件里的 bug 修复：

```text
先用 $runtime-bug-triage 定位 chat runtime 状态异常，再用 $large-file-split-advisor 判断 services/core/app/api/chat_routes.py 这轮到底应该局部修还是先拆一层。不要一开始就大重构。
```

#### 3. 先查依赖边界，再决定如何改

适合 mempalace / chromadb / pypdf：

```text
先用 $optional-dependency-boundary-check 看当前 memory 能力有没有把 mempalace 扩散进核心路径；如果边界没问题，再用 $core-change-entrypoint 找到这轮真正该改的 adapter 或 repository 落点。
```

#### 4. 做减法时带上本体约束

适合收敛项目范围：

```text
先用 $project-simplifier 评估当前前后端主链路和删除候选；如果某些删改涉及 goals、memory 或 persona 的长期表达，再补一次 $xiao-yan-architecture-guardian，确认不会把小晏做成纯工具平台。
```

#### 5. 改完统一收尾

适合任何实现完成后的最后一步：

```text
这轮改动已经做完了，最后用 $docs-and-tests-sync-guard 检查 docs、tests、runbook、skills 文档和验证命令是否都同步了，并明确告诉我还剩什么风险。
```

## 维护建议

- 新增 skill 时，优先补齐 `SKILL.md`、`agents/openai.yaml`、图标资源。
- 更新 skill 行为时，优先同步本页，避免“skill 已变，但首页清单没跟上”。
- 如果未来 skill 超过 10 个，建议按“架构 / 排障 / 收敛 / 收尾”分组再扩展本页。
