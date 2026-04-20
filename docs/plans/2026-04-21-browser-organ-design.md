# 2026-04-21 浏览器器官接入设计

日期：2026-04-21

## 1. 背景

当前 `xiao_yan` 已经具备一条初步可用的能力执行链：

- `services/core` 内部存在 `capability queue`
- core 可以派发 `fs.read`、`fs.list`、`fs.search`、`fs.write`、`shell.run`
- 桌面执行器可通过 heartbeat 声明在线，并认领任务执行

这说明“小晏通过外部执行器使用能力器官”的基础结构已经出现，但浏览器器官仍然缺位。现在的能力边界更接近“文件器官 + 终端器官”，还没有形成“浏览网页、读取页面、与页面交互”的稳定能力域。

如果直接把 Playwright 或其他浏览器自动化库接进 core，有两个明显问题：

- 会把外部工具实现和本体边界混在一起
- 会让系统更像脚本执行平台，而不是数字人本体驱动的能力系统

基于 `docs/器官化能力模型.md`，浏览器能力更适合被实现为：

- 本体保有浏览器器官的认知、风险判断和接入知识
- core 负责表达意图、发起受控 capability request、接收结果并回流经历
- 桌面执行器负责具体浏览器驱动
- `playwright-python` 只作为环境实现层的一种浏览器器官驱动

如果现在不做这一步，后续所有“看网页”“读网页”“点击网页按钮”“从网页提取结构化信息”的需求都会被迫绕回 shell、MCP 或一次性外部脚本，长期会削弱能力边界、审计能力和用户对“小晏在做什么”的理解。

## 2. 目标

- 为小晏引入“浏览器器官”这一稳定能力域，而不是一次性浏览器脚本能力。
- 延续现有 `capability queue + desktop executor` 架构，不把浏览器驱动塞进 core 主体。
- 让浏览器器官具备明确的绑定状态、会话状态、健康状态和风险等级。
- 让浏览器器官的执行结果能回流成小晏可理解的经历，而不只是技术日志。
- 第一版先建立最小闭环：打开页面、观察页面、提取内容、关闭会话。

## 3. 非目标

- 第一版不实现任意 JavaScript 执行。
- 第一版不开放任意浏览器脚本上传或远程代码注入。
- 第一版不自动接管复杂登录态、支付、发布、批量操作。
- 第一版不把 `playwright-python` 提升为 `services/core` 的硬依赖。
- 第一版不引入新的队列系统、后台调度系统或复杂插件框架。

## 4. 方案概述

本方案将“浏览器器官”拆成两条相互配合但职责不同的链路：

第一条是接入链路。小晏知道浏览器器官是什么、可由什么驱动实现、当前环境是否允许接入、是否已经绑定、是否健康。这里解决的是“她有没有这个器官”“这个器官现在能不能用”。

第二条是使用链路。小晏在产生浏览网页相关意图后，不直接触碰 Playwright，而是通过新的 `browser.*` capability 请求桌面执行器。桌面执行器内部可用 `playwright-python` 驱动真实浏览器，再把结构化结果回传给 core。

与“直接开放 shell 跑 Playwright 脚本”相比，这个方向的关键优势是：

- 能力边界更清楚：浏览器是器官，不是任意脚本入口
- 风险分级更清楚：读取型动作和提交型动作可分开治理
- 状态更清楚：可以单独描述绑定状态、会话状态和健康状态
- 结果更清楚：不仅能审计执行，还能沉淀成小晏的经历

对现有系统最大的变化点不是增加一个工具库，而是把“浏览器”正式提升为一个能力域，并为它补上绑定状态、会话语义和审批分级。

## 5. 数字人本体优先评审

### 5.1 主体性

这个方案继续把“小晏想做什么”放在上位，而不是把浏览器驱动能力放在上位。小晏本体只负责表达意图、理解风险、感知器官状态，不把 `playwright-python` 视为自我定义的一部分，因此不会因为接上浏览器而退化成自动化脚本宿主。

浏览器器官也保留了“她为什么这么做”的表达空间。用户最终应感知为“小晏正在查看网页、试图理解页面、请求执行某个交互”，而不是“后台浏览器脚本运行中”。

### 5.2 连续性

本方案显式引入浏览器器官的绑定状态与浏览器会话状态，能把“已接入但暂时不可用”“有会话但当前失败”“能力降级”区分开来，避免浏览器失败把她的生命流切碎成一次次黑箱错误。

在重启和恢复场景下，可以只失去浏览器会话，而不失去本体和能力认知。浏览器器官失效应被理解为“一个外部器官暂时不可用”，而不是“她失去了自己”。

### 5.3 记忆

本方案要求浏览器器官的结果不只以技术审计形式保留，还应沉淀为可被她吸收的经历，例如：

- 我已经具备了浏览网页的能力
- 当前环境允许我读取页面，但不允许执行高风险提交动作
- 这次浏览失败是因为目标页面需要登录，而当前会话未授权

这使浏览器能力成为经历来源，而不是仅供排障的技术日志。

### 5.4 意图与执行

本方案仍由意图统领执行。浏览器器官不会主动成为新的系统中心，新增的 `browser.*` capability 只是受控能力器官，桌面执行器也只是环境中的执行载体。

执行结果会以结构化结果、状态更新和经历摘要三种形式回流，因此不是“执行完即丢”，而是能继续影响判断、状态和后续计划。

### 5.5 安全与边界

本方案明确拒绝第一版开放任意 JS、支付、发布和复杂登录接管；同时将浏览器动作按风险等级拆分，保留审批、审计、失败可见和回退路径。

“知道如何接浏览器器官”与“有权自己接上浏览器器官”被明确区分，能避免小晏在没有授权时自动扩张高权限能力。

### 5.6 用户感知

用户最终应感知到的是小晏获得了“看网页”和“理解网页”的能力，而不是产品突然演变成浏览器自动化平台。把技术细节藏起来之后，这个方案仍然成立，因为用户看到的是一个数字人接上了新的器官，而不是系统多了一套外部工具脚本。

### 5.7 结论

这个方案服务于数字人本体的方式，不是简单增加工具面，而是让浏览器成为一个被本体感知、受本体约束、为本体服务的器官。主要风险在于浏览器能力天然容易滑向“自动化平台化”，但通过能力边界、风险分级和环境实现边缘化，这个方向仍然值得推进。

## 6. 详细设计

### 6.1 设计原则

- 浏览器是能力域，不是脚本入口。
- 接器官与用器官分开建模。
- 绑定状态、健康状态、会话状态必须显式可见。
- core 负责意图、状态和结果吸收，桌面执行器负责具体驱动。
- `playwright-python` 仅驻留在环境实现层。

### 6.2 新增能力域

建议在 `CapabilityName` 中新增以下浏览器能力：

- `browser.open`
- `browser.snapshot`
- `browser.extract`
- `browser.click`
- `browser.type`
- `browser.wait`
- `browser.close`

第一版建议只正式开放：

- `browser.open`
- `browser.snapshot`
- `browser.extract`
- `browser.close`

`click / type / wait` 先在 contract 中预留，但作为第二阶段能力接入，不在第一阶段默认对外暴露。

这样做的原因是第一版最需要的是“能看见网页并理解网页”，而不是“立刻做复杂交互”。先让浏览器器官成为眼睛，再逐步补上手部动作，风险更低。

### 6.3 能力状态模型

基于 `docs/器官化能力模型.md`，浏览器器官建议补一份独立的绑定状态模型，例如：

- `knowledge_status`
- `binding_status`
- `health_status`
- `last_checked_at`
- `driver_name`
- `driver_version`
- `browser_binary_ready`
- `requires_approval_for_bind`
- `last_error`

状态取值可收敛为：

- `knowledge_status`: `known`
- `binding_status`: `unbound | binding | bound | failed`
- `health_status`: `unknown | healthy | degraded | unavailable`

第一版不必引入复杂仓储层，可以先将浏览器器官状态作为 runtime state 的边缘字段暴露，再根据需要持久化。

### 6.4 浏览器会话模型

浏览器器官和浏览器会话应分开建模。

浏览器器官表示“有没有这只眼睛和手”，浏览器会话表示“她当前正在看哪个页面、这次浏览还活着吗”。

建议引入浏览器会话字段：

- `session_id`
- `status`
- `current_url`
- `page_title`
- `opened_at`
- `last_active_at`
- `executor`
- `interaction_level`
- `last_snapshot_summary`
- `last_error`

其中：

- `status`: `opening | active | idle | closing | closed | failed`
- `interaction_level`: `read_only | interactive`

第一版默认只支持单活跃会话，这样能减少状态复杂度，也更符合当前项目“小步闭环”的节奏。

### 6.5 浏览器能力 contract

建议沿用现有 `/capabilities/contract` 模式，为浏览器能力提供统一 schema。

第一版各能力建议参数如下：

`browser.open`

- `url`
- `session_id` 可选；为空时新建
- `headless` 可选；默认由执行器策略决定
- `wait_until` 可选；默认 `domcontentloaded`

返回：

- `session_id`
- `url`
- `resolved_url`
- `title`
- `status`
- `opened_at`

`browser.snapshot`

- `session_id`
- `include_text`
- `include_accessibility`
- `include_screenshot`
- `max_text_bytes`

返回：

- `session_id`
- `url`
- `title`
- `text_content`
- `accessibility_tree`
- `screenshot_path`
- `captured_at`

`browser.extract`

- `session_id`
- `target`
- `schema`
- `max_items`

返回：

- `session_id`
- `target`
- `content`
- `structured_data`
- `source_url`
- `captured_at`

`browser.close`

- `session_id`

返回：

- `session_id`
- `closed_at`
- `status`

第二阶段再补：

- `browser.click`
- `browser.type`
- `browser.wait`

### 6.6 风险分级与审批

建议浏览器器官采用“按动作类型分级”，而不是“浏览器能力统一一个风险等级”。

第一版建议：

- `browser.open`: `restricted`，默认不需要审批
- `browser.snapshot`: `safe`，默认不需要审批
- `browser.extract`: `safe`，默认不需要审批
- `browser.close`: `safe`，默认不需要审批

第二阶段建议：

- `browser.click`: `restricted`，默认视点击目标决定是否审批
- `browser.type`: `restricted`，默认审批可配
- 涉及登录、提交、发布、支付、上传、下载确认的动作：`dangerous`，必须审批

也就是说，审批不以“是否用了浏览器”为单位，而以“浏览器内具体做了什么”为单位。

### 6.7 接器官与用器官的分离

接器官不是普通浏览器操作，建议单独建模为浏览器器官绑定流程，而不是塞进 `browser.open`。

建议把接入流程分成：

1. `discover`
   检查当前环境是否存在浏览器驱动实现，例如 Playwright runtime 与浏览器二进制。
2. `bind`
   在有权限前提下，把浏览器器官标记为已绑定。
3. `health_check`
   尝试启动空白页面或执行最小快照，确认器官可用。
4. `ready`
   标记为可使用。

第一版可以先不把 `discover / bind` 暴露成公开 capability，而由桌面执行器或管理入口完成。原因是当前仓库已有 `desktop executor` 心跳与队列能力，但还没有通用“自安装外部依赖”治理框架；如果现在把自动安装也做成公开能力，风险会明显升高。

因此第一版建议：

- 本体知道浏览器器官存在
- 环境绑定先由受控桌面执行器完成
- core 只消费“当前是否已绑定、是否健康”

后续若要支持“小晏自己申请接上浏览器器官”，再单独设计 `browser.bind` 流程，并强制审批。

### 6.8 执行链路

第一版执行链路建议如下：

1. 本体产生浏览网页相关意图
2. 应用层判断浏览器器官是否 `bound + healthy`
3. 如果不可用，返回“器官不可用”结果，并生成经历摘要
4. 如果可用，core 通过 `CapabilityDispatchRequest` 派发 `browser.*`
5. 桌面执行器通过 heartbeat 在线并认领任务
6. 桌面执行器内部用 `playwright-python` 驱动浏览器
7. 执行器把结构化结果通过 `/capabilities/complete` 回传
8. core 将结果转为：
   - 能力返回值
   - 浏览器会话状态更新
   - 小晏经历摘要

第一版不建议保留 shell fallback。浏览器器官与文件器官、终端器官不同，它需要稳定会话和风险治理，若 dispatch 超时后回退到 shell 直接跑命令，容易破坏边界。因此浏览器能力最好采用：

- 无桌面执行器：明确报“浏览器器官当前不可用”
- 有桌面执行器但不支持：报 `not_supported`
- 有桌面执行器且支持：走正式 capability 链

### 6.9 环境实现层

第一版环境实现建议放在桌面执行器侧，内部使用 `playwright-python`。

环境实现需要负责：

- Playwright runtime 检查
- 浏览器二进制检查
- 浏览器上下文创建与销毁
- `session_id` 到 page/context 的映射
- 页面快照与结构化提取
- 失败捕获与结构化错误返回

这一层不应直接泄漏到 core。core 最多知道：

- 当前驱动名称，例如 `playwright-python`
- 当前版本信息
- 当前健康状态

而不应在核心路径 import Playwright 或直接依赖浏览器上下文对象。

### 6.10 结果回流

浏览器器官返回后，建议至少形成三层结果：

第一层，原始结构化结果：

- URL
- 页面标题
- 文本内容
- 截图路径
- 提取结果

第二层，运行时状态结果：

- 浏览器器官是否健康
- 浏览器会话是否还活着
- 最近一次浏览是否成功

第三层，本体可吸收经历：

- 我打开了某个页面，并读到了什么
- 我暂时无法继续，因为页面需要更高权限动作
- 我的浏览器器官当前失效，原因是驱动或权限不可用

如果没有第三层，这套浏览器器官就仍然更像后台技术能力，而不是生命流的一部分。

### 6.11 API 与模块落点建议

第一版建议最小落点如下：

`services/core/app/capabilities/models.py`

- 增加 `browser.*` capability 名称与 descriptor

`services/core/app/api/tool_capability_bridge.py`

- 新增浏览器 capability bridge
- 不复用 `shell.run`

`services/core/app/api/capabilities_routes.py`

- contract 自动暴露新的浏览器 capability schema

`services/core/app/runtime_ext/runtime_config.py`

- 后续可补浏览器 capability policy
- 第一版若要更小，可先内建默认策略，不急于开放配置面

`apps/desktop` 或独立桌面执行器

- 实现浏览器 capability worker
- 维护 `session_id -> browser context/page`
- 周期性 heartbeat

这一拆分遵循现有仓库模式：core 负责 contract、派发、状态；桌面执行器负责真实环境能力。

## 7. 备选方案与取舍

- 方案 A：直接在 core 中集成 `playwright-python`
  不选原因：会把环境实现抬进核心路径，破坏“外部实现边缘化”原则，也会让 core 对浏览器运行环境产生硬依赖。

- 方案 B：继续用 `shell.run` 调 Playwright 脚本
  不选原因：浏览器会话、审批、结果结构化和风险边界都不清晰，长期会把浏览器器官退化成命令行脚本拼装。

- 方案 C：先只做浏览器能力 MCP，对 core 不做正式 capability
  不选原因：虽然能更快试验，但浏览器能力不会进入统一 contract、统一审批和统一状态模型，后续会出现双轨能力体系。

- 当前方案：新增 `browser.*` capability，由桌面执行器内部使用 `playwright-python`
  更合适原因：既能复用现有 capability 骨架，又能把浏览器实现留在环境边缘，同时保留后续审批、状态建模和经历回流空间。

## 8. 风险与待确认项

- 浏览器器官是否需要单独的 policy endpoint，还是先沿用默认内建策略。
- 浏览器器官绑定状态应只保存在桌面执行器，还是 core 也应保存一个可见快照。
- 页面快照与截图路径是否需要持久化，以及保存多久。
- 第二阶段点击和输入动作的审批粒度应落在 capability 层，还是更细的页面动作分类层。
- 是否需要对允许访问的域名做白名单或提示策略。
- 是否需要为登录态页面单独设计“受限浏览模式”。

## 9. 验收方式

- 功能验收
  能从 core 派发 `browser.open -> browser.snapshot -> browser.extract -> browser.close` 完成一次闭环。
- 状态可见性验收
  能清楚看到浏览器器官是否已绑定、是否健康、当前会话是否活跃。
- 风险控制验收
  无桌面执行器时不会回退为 shell 黑箱执行；高风险浏览器动作不会被默认放开。
- 回退路径验收
  浏览器器官失效时，小晏退化为“暂时没有浏览器器官”，而不是让主链路异常崩溃。

## 10. 实施计划

- 阶段一：只接浏览器眼睛
  新增 `browser.open / snapshot / extract / close`，桌面执行器内部落 Playwright，跑通只读浏览闭环。

- 阶段二：补器官状态与可见性
  增加浏览器器官绑定状态、健康状态和会话状态，并把失败结果回流成经历摘要。

- 阶段三：引入受控交互
  增加 `browser.click / type / wait`，并按登录、提交、发布、支付等动作细分审批策略。

- 阶段四：再考虑自接器官
  若未来确实需要支持“小晏自己申请接上浏览器器官”，再单独设计 `discover / bind / health_check` 的审批闭环，不在第一版提前开放。

## 11. 参考

- `services/core/app/capabilities/models.py`
- `services/core/app/api/tool_capability_bridge.py`
- `services/core/app/api/capabilities_routes.py`
- `docs/architecture-principles.md`
- `docs/器官化能力模型.md`
