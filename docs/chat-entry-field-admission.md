# `ChatEntry` 字段准入规则

本文用于约束 `apps/desktop` 聊天主链里，什么字段可以进入 `ChatEntry`，什么字段不应该进入。

适用范围：

- [apps/desktop/src/components/chat/chatTypes.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/chat/chatTypes.ts)
- [apps/desktop/src/lib/chatMessages.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/lib/chatMessages.ts)
- [apps/desktop/src/components/chat/ChatMessages.tsx](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/chat/ChatMessages.tsx)
- [apps/desktop/src/components/app/chatRealtimeUpdates.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/app/chatRealtimeUpdates.ts)
- [apps/desktop/src/components/app/runtimeRealtimeUpdates.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/app/runtimeRealtimeUpdates.ts)

## 1. 核心原则

`ChatEntry` 代表“聊天区里一条正在被用户阅读和操作的消息”，不是一个通用事件容器，也不是调试信息承载体。

任何字段想进入 `ChatEntry`，都必须满足下面两个前提：

1. 它直接服务于当前这条消息的阅读连续性、恢复连续性或必要上下文。
2. 它值得跨过 `App.tsx -> chatMessages.ts -> ChatMessages.tsx` 这整条链一起维护。

如果一个字段只是“系统知道了什么”，但不改变用户此刻对这条消息的理解或交互，它就不应该进入 `ChatEntry`。

## 2. `ChatEntry` 允许承载的 5 类字段

当前 `ChatEntry` 只允许承载以下 5 类字段：

### 2.1 Message Core

定义：消息本体，用户和小晏真正说出来的内容。

允许字段：

- `id`
- `role`
- `content`

判断标准：

- 去掉这些字段，这条消息就不再成立。

### 2.2 Lifecycle

定义：这条消息当前正处在什么发送/流式/失败阶段。

允许字段：

- `state`
- `streamSequence`
- `errorMessage`

判断标准：

- 字段直接影响“这条消息现在怎么显示”或“是否仍然处于未完成过程态”。

### 2.3 Linkage

定义：把本地消息、realtime 事件、runtime history 重新对齐所必需的链路锚点。

允许字段：

- `requestKey`
- `reasoningSessionId`

判断标准：

- 字段参与去重、对齐、补丁或 resume，而不是单纯为了排障观察。

### 2.4 Recovery

定义：用户需要继续完成这条消息时，最小恢复动作所必需的数据。

允许字段：

- `requestMessage`
- `retryRequestBody`

判断标准：

- 没有这个字段，就无法在原消息上“重新发送”或“接着说完”。

### 2.5 Enrichments

定义：附着在这条消息上的、对阅读有价值但不属于消息本体的上下文。

允许字段：

- `reasoningState`
- `knowledgeReferences`
- `relatedMemories`

判断标准：

- 字段必须是“围绕当前这条回复”的附属上下文，而不是系统全局状态。
- 默认不应该抢占消息主视觉。
- 必须允许被折叠、降级或完全隐藏，而不破坏主回复成立。

## 3. 明确禁止进入 `ChatEntry` 的字段类型

下面这些类型默认禁止进入 `ChatEntry`。

### 3.1 Transport / Debug / Observability 字段

例如：

- websocket `timestamp_ms`
- `response_id`
- queue position
- tracing id
- provider name
- latency
- retry count
- raw session diagnostics

原因：

- 这些字段服务排障和观测，不服务消息阅读。
- 一旦进入 `ChatEntry`，后续极容易被 UI 消费，聊天区会继续滑向工具控制台。

归属建议：

- realtime payload
- logger / telemetry
- 单独的 runtime debug state

### 3.2 Tool / Capability 执行细节

例如：

- tool 原始输入输出
- capability fallback trace
- provider downgrade reason
- sandbox / permission trace
- command stderr excerpt

原因：

- 它们描述的是系统执行过程，不是消息本身。
- 即使与某条回复相关，也应该先停留在 tool/capability 专属状态，而不是直接进入聊天主消息对象。

归属建议：

- capability panel
- tool execution model
- 单独的 assistant artifact / sidecar state

### 3.3 局部 UI 状态

例如：

- 是否展开 memory
- 是否展开 knowledge
- hover / selected / highlighted
- “本条消息是否显示调试块”

原因：

- 这些状态属于组件本地显示控制，不属于消息数据。

归属建议：

- `useState`
- `useChatPanelState`
- 单独的 UI store

### 3.4 与整页或整会话相关，但不属于单条消息的状态

例如：

- 当前是否正在发送任意消息
- 全局错误 banner
- 当前 chat route 是否激活
- 当前人格/内在世界状态

原因：

- 这些信息不是“这条消息”的属性。

归属建议：

- `App.tsx`
- page/container state
- runtime state

## 4. 新字段准入判断流程

以后新增字段时，必须按下面顺序判断。

### Step 1. 它属于哪一类

只允许落入下面 5 类之一：

- Message Core
- Lifecycle
- Linkage
- Recovery
- Enrichments

如果不属于这 5 类，默认不能进 `ChatEntry`。

### Step 2. 它是否直接服务当前消息

必须回答：

- 去掉这个字段，当前这条消息的阅读是否受损？
- 去掉这个字段，当前这条消息的恢复是否受损？
- 去掉这个字段，当前这条消息的对齐/去重是否受损？

如果三个答案都是否，这个字段不能进。

### Step 3. 它会不会推高“小晏被系统状态包围”的风险

必须回答：

- 这个字段未来是否很容易被直接显示到主气泡附近？
- 它是否会让用户更先看到系统过程，而不是小晏的表达？

如果答案偏“会”，默认不能直接进 `ChatEntry`。

### Step 4. 它是否值得维护整条跨层链

进入 `ChatEntry` 意味着至少要同步考虑：

- `chatTypes.ts`
- `chatMessagePresentation.ts`
- `chatMessages.ts`
- `chatMessageMutations.ts`
- `chatRealtimeUpdates.ts` 或 `runtimeRealtimeUpdates.ts`
- `ChatMessages.tsx`
- 相关测试

如果一个字段不值得维护这整条链，它就不应该进。

## 5. 进入 `ChatEntry` 后的配套要求

任何新字段一旦进入 `ChatEntry`，必须同时完成下面几件事：

1. 在 [chatTypes.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/chat/chatTypes.ts) 中放入明确类别，不允许无归属裸加。
2. 判断它属于：
   - 消息补丁字段
   - runtime 回放字段
   - 展示解释字段
   - 仅恢复字段
3. 明确它是否需要进入：
   - [chatMessageMutations.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/lib/chatMessageMutations.ts)
   - [chatRealtimeUpdates.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/app/chatRealtimeUpdates.ts)
   - [runtimeRealtimeUpdates.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/app/runtimeRealtimeUpdates.ts)
   - [chatMessagePresentation.ts](/Users/ldy/Desktop/work/xiao_yan/apps/desktop/src/components/chat/chatMessagePresentation.ts)
4. 如果字段可见，必须先定义“默认显示 / 折叠显示 / 完全不显示”的规则。
5. 补测试，至少覆盖：
   - 字段如何被写入
   - runtime 回放是否保留/清理
   - UI 是否按预期显示或不显示

## 6. 当前 `ChatEntry` 字段归属清单

### Message Core

- `id`
- `role`
- `content`

### Lifecycle

- `state`
- `streamSequence`
- `errorMessage`

### Linkage

- `requestKey`
- `reasoningSessionId`

### Recovery

- `requestMessage`
- `retryRequestBody`

### Enrichments

- `reasoningState`
- `knowledgeReferences`
- `relatedMemories`

## 7. 未来字段的推荐归宿

### 可以考虑进入 `ChatEntry`，但必须谨慎

- “这条回复引用了哪些记忆片段”的轻量摘要
- “这条回复的工具结果摘要”，前提是它会真正改变回复阅读，而不是只服务排障

### 默认不要进入 `ChatEntry`

- tool 原始 trace
- fallback 内部原因
- model/provider 选择细节
- token / latency / debug counters
- 后端排序分数
- 检索原始命中列表
- 任意“仅为了以后可能会展示”的预埋字段

## 8. 最后一条判断口令

新增字段前，先问一句：

“它是在帮助用户更连续地感受小晏正在说什么，还是在帮助系统记录自己做了什么？”

如果更接近后者，就不要放进 `ChatEntry`。
