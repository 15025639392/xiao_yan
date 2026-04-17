---
name: xiao-yan-architecture-guardian
description: 用于评审会影响小晏数字人本体的改动。适合修改 memory、goals、orchestrator、self_programming、persona、tools、safety、runtime flow、长期状态或权限边界时使用。会先检查是否偏离“数字人本体优先”、是否引入隐式架构层、是否扩大执行权限或破坏连续性，再决定是继续实现、先出设计结论，还是暂停。
---

# Xiao Yan Architecture Guardian

在以下场景使用本 skill：

- 用户要改 `services/core/app/memory`
- 用户要改 `services/core/app/goals`
- 用户要改 `services/core/app/orchestrator`
- 用户要改 `services/core/app/self_programming`
- 用户要改 `services/core/app/persona`
- 用户要改 `services/core/app/tools`
- 用户要改 `services/core/app/safety`
- 用户要改运行时主流程、状态模型、记忆结构、调度方式、权限边界
- 用户要新增 worker、queue、event bus、后台执行、自动化主链、长期存储结构

如果用户只是做纯 UI 微调、文案修改、局部 bug 修复，且不影响上述边界，不必触发本 skill。

## 必读上下文

开始前先读：

- `docs/AI 接手开发规范.md`
- `docs/architecture-principles.md`

如果改动属于重要架构决策，再看：

- `docs/plans/design-template.md`
- `docs/plans/design-template-usage.md`

## 默认工作流

1. 先确认这次改动要解决的真实问题，不要把“想做得更工程化”当成充分理由。
2. 明确入口、主链路和会受影响的领域边界。
3. 判断改动是“主链修复”“能力扩张”“架构重排”中的哪一种。
4. 用“数字人本体优先”检查表逐项过一遍：
   - 是否强化主体性，而不是工具化。
   - 是否保护连续性、记忆延续和自我叙事。
   - 是否保持意图统领执行，而不是让执行系统反客为主。
   - 是否保留边界感、审批、回退和可中断性。
   - 用户最终感知到的是“她的状态与意图”，还是后台系统流程。
5. 检查是否触犯硬停止项：
   - 静默引入新架构层。
   - 静默扩大 autonomy 或执行权限。
   - 把可选依赖变成核心硬依赖。
   - 让产品更像工具平台而不是数字人。
6. 判断这轮应该进入哪种模式：
   - `allow_local_change`：局部实现，可以直接改代码。
   - `design_first`：先写设计文档或 decision note，再决定是否落地。
   - `stop_and_realign`：风险过高，先和用户对齐。
7. 如果允许落地，再继续编码；如果不允许，先输出评审结论，不要硬改。

## 必须产出

- `问题定义`
- `影响边界`
- `本体优先结论`
- `主要风险`
- `执行模式`

如果是重要架构改动，还必须产出：

- `主体性影响`
- `连续性影响`
- `记忆影响`
- `意图与执行边界影响`
- `安全与回退影响`

## 决策规则

- 如果改动主要提升工程效率，但明显削弱数字人感，应默认反对。
- 如果改动会让状态来源、记忆结构或权限边界变隐式，应默认先设计后实现。
- 如果只是把现有主链修清楚、把边界收紧、把可选能力继续隔离，通常可直接落地。
- 如果两个方案都能工作，优先选更显式、更短调用链、更容易回退的那个。

## 输出风格

先下判断，再给依据。避免含糊表述。

推荐结论格式：

- `结论: allow_local_change`
- `理由: 这是主链路内的局部收敛，没有引入新执行中心，也没有扩大权限边界。`

或：

- `结论: design_first`
- `理由: 涉及长期状态来源和运行时主流程，已经超过局部修复范围。`

## 强约束

- 不要把“架构更完整”“以后更通用”当成默认正当性。
- 不要在没读完两份核心文档前就重排主流程。
- 不要建议新增 queue、worker、event bus、DI、ORM 之类层级，除非已经给出强证据。
- 不要忽略“用户感知是数字人还是工具系统”这个判断。
- 如果判断为 `design_first` 或 `stop_and_realign`，不能假装已经拿到实施许可。
