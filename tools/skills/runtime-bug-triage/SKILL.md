---
name: runtime-bug-triage
description: 用于排查 xiao_yan 主链路运行问题的证据化工作流。适合 chat、persona、goals、world、memory、tools、API 或状态同步异常时使用。会先复现、收集链路证据、缩小故障层级，再决定最小修复面和需要补的测试，而不是一上来猜着改。
---

# Runtime Bug Triage

在用户反馈“能跑但不对”“状态不对”“某段链路失效”“偶发异常”“对话和状态不同步”时使用本 skill。

## 适用范围

- chat 行为异常
- persona / world 状态不符合预期
- goal 生成、 admission、 focus、状态流转异常
- memory 写入、召回、降级行为异常
- tool 调用、权限、sandbox、结果回流异常
- API 返回和前端显示不一致

## 目标

先拿证据，再下结论，再修最小面。

## 低 Token 默认做法

项目初期排 bug 时，优先缩小证据面，而不是扩大扫描面。

默认只看：

- 真实复现输入
- 实际入口
- 最短行为链
- 直接相关状态与测试

默认不做：

- 没有证据时全仓搜相似问题
- 顺手检查无关模块
- 在定位前就扩成架构分析

## 默认排查顺序

按下面顺序缩小范围，不要跳步：

1. `复现`
   - 明确输入、环境、期望结果、实际结果
   - 如果无法稳定复现，记录不稳定条件
2. `入口`
   - 找到实际进入的 route / command / runtime tick
3. `链路`
   - 顺着 `api -> service -> repository/gateway -> state` 走一遍
4. `状态`
   - 检查相关模型、持久化文件、关键字段是否已经在上游偏掉
5. `降级`
   - 如果涉及可选依赖，检查是不是降级路径触发了不同表现
6. `边界`
   - 检查是不是权限、审批、sandbox 或防护逻辑拦住了行为
7. `修复面`
   - 只改第一个被证据确认的错误层，不要一路连修

## 主链路提示

针对这个仓库，优先按下面的方向排：

- 对话问题：`chat -> persona -> goals/world -> memory`
- 目标问题：`goal trigger -> admission -> persistence -> active/focus sync`
- 工具问题：`tool request -> sandbox -> runner -> result mapping -> state feedback`
- 状态问题：`api response -> service assembly -> state file / model -> frontend consumer`

## 必须产出

- `复现描述`
- `实际链路`
- `证据点`
- `根因判断`
- `最小修复面`
- `测试补位`

推荐格式：

- `复现描述: ...`
- `实际链路: chat_routes -> ChatService -> GoalAdmissionService -> goal repository`
- `证据点: admission 返回 defer，但前端仍按 active 展示`
- `根因判断: 状态映射层漏处理 defer`
- `最小修复面: response mapper`
- `测试补位: 增加 defer 分支断言`

## 修复原则

- 优先修“状态被错误表达”而不是先改生成逻辑。
- 优先修“单层映射错误”而不是重写整条链。
- 如果是降级路径问题，先保住可运行和清晰提示，不要急着补重依赖。
- 如果根因未证实，不要把猜测包装成结论。

## 强约束

- 不要直接根据日志关键词猜根因。
- 不要因为看到大文件就顺手重构整段链路。
- 不要同时改两个可疑层，除非已有证据证明它们必须一起改。
- 如果没有复现，只能给“当前最可能原因”和“待补证据”，不能伪装成已定位。
