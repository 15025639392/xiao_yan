# 项目长期记忆

## 数字人自编程系统（services/core/app/self_improvement）

- 技术栈：Python 3.11 + Pydantic + pytest
- 架构：Planner → Executor → Service 三层

### 自编程能力三阶段完成（2026-04-05）

**Phase 1: LLM 补丁生成器** ✅
- LLMPlanner 包装 ChatGateway，结构化 JSON 输出补丁
- 支持 REPLACE/CREATE/INSERT 三种编辑类型
- 安全护栏禁止修改核心模块
- 向后兼容：无 API Key 时行为不变

**Phase 2: 多候选评分选优** ✅
- CandidateScorer 4 维度评分（confidence/risk/simplicity/safety）
- Executor.try_best() A/B 测试模式
- Service 层自动检测 plan_all 并走多候选路径

**Phase 3: Git 工作流 + 新文件能力** ✅
- GitWorkflowManager：分支管理、自动 commit、回滚、合并
- commit message 结构化：`[self-fix] {area}: {summary}` 含 Job ID 和 Candidate label
- Executor.commit_job() 在 APPLIED 后自动 create_branch → stage → commit
- CREATE kind 增强：LLM 提示词要求生成完整可运行代码
- 安全原则：从不 push/force-push/amend，dry_run 模式可用

**测试总计：180 passed, 0 failed**

**Phase 4: 安全沙箱 + 冲突检测 + 历史记录（2026-04-05）✅**
- SandboxEnvironment：隔离临时目录预验证补丁（超时/资源限制/自动清理）
- ConflictDetector：受保护路径 BLOCKING、文件重叠 WARNING、循环自改 WARNING
- SelfImprovementHistory：内存/JSON 文件双后端，完整审计追踪
- Executor.preflight_check()：apply 前一步完成冲突+沙箱预检
- 智能降级：沙箱环境不完整时跳过而非阻塞（向后兼容）

**四阶段总计：222 passed, 0 failed**

**Phase 5: 回滚恢复 + 健康检查/自愈闭环（2026-04-05）✅**
- RollbackRecovery：差异快照（apply 前自动保存原始文件状态）+ 精确回滚
- RollbackPlan/RollbackResult：回滚计划和结果数据模型，含级联依赖检测
- HealthChecker：5 维度健康评分（测试通过率35%/自编程频率20%/回滚率20%/冲突率15%/文件稳定性10%）
- HealthReport：综合健康报告 + 等级(excellent/good/fair/poor/critical) + 趋势判断 + 回滚建议
- Executor 集成：apply 前自动快照 + smart_rollback() API
- Service 集成：APPLIED 后自动健康评估，低分时标记回滚建议

**五阶段总计：275 passed, 0 failed**

**Phase 6: 审批交互系统（2026-04-05）✅**
- 新增 `PENDING_APPROVAL` + `REJECTED` 状态枚举
- Service 层门控：apply 后不再直接 VERIFYING，先进入 pending_approval 等待用户操作
- 3 个审批 API：GET /pending（查询）、POST /approve（批准→VERIFYING）、POST /reject（拒绝→REJECTED）
- 前端 ApprovalPanel：展示变更摘要 + 文件列表 + Diff 查看器 + 批准/拒绝按钮（拒绝需填原因）
- StatusPanel 自动检测 pending_approval 状态并切换渲染 ApprovalPanel

**六阶段总计：TypeScript 0 错误，后端 lint 通过**

**Phase 6 测试补全 + 导入修复（2026-04-05）✅**
- 修复 main.py 缺失导入（Any/logger/datetime/WorldRepository/WorldStateService）导致 7 个测试文件无法 collect
- 适配 test_self_improvement_service.py 7 个测试到 PENDING_APPROVAL 门控（_approve_pending_job 辅助函数）
- 新增 test_phase6_approval.py 14 个测试（审批 API、状态门控、辅助函数）
- **最终: 288 passed, 0 failed**

**Phase 7: 人格内核系统（2026-04-05）✅**
- 核心目标：让数字人有"性格"，不再回复模板拼接内容
- PersonaProfile 数据模型：大五人格(OCEAN) + 说话风格 + 价值观 + 动态情绪状态(12种情绪×5级强度)
- EmotionEngine：事件驱动情绪累积 + 时间衰减 + 性格影响幅度 + 多源推断(chat/goal/self_improvement)
- PersonaService：CRUD + JSON 持久化 + 人格感知 prompt 生成 + 向后兼容
- 前端：PersonaCard（状态面板情绪卡片+心情条+事件流）+ PersonaSettings（设置页3 Tab配置面板）
- API: 11 个新端点 (GET/PUT /persona*, GET/POST /persona/emotion*)
- **最终: 347 passed, 0 failed**（+59 新测试，零回归）
- Pydantic v2 注意：model_copy() 必须用 `update=` 参数而非直接传关键字参数

**Phase 8: 记忆与人格联动系统（2026-04-05）✅**
- 核心目标：让数字人从"失忆的聊天机器人"变成"有记忆的个体"
- MemoryEntry 数据模型：5 种记忆类型(fact/episodic/semantic/emotional/chat_raw) + 5 级强度(faint→core) + retention_score 保留分值
- MemoryService：CRUD + 对话自动提取(偏好/约定/情绪检测) + 人格感知检索排序 + prompt 注入
- chat 端点改造：回复后自动 extract_from_conversation() + 记忆上下文注入 prompt
- 前端：MemoryPanel（时间线+搜索+类型过滤+骨架屏）+ memory.css 样式
- API: 8 个新端点 (GET/POST /memory*)
- **最终: 390 passed, 0 failed**（+43 新测试，零回归）
- 注意：MemoryEvent.to_entry() 需包含所有新 kind 映射，fact 类型默认 importance=6

**Phase 9: 情绪→表达风格深层映射（2026-04-05）✅**
- 核心问题：Phase 7 情绪引擎只输出"你现在开心"的状态描述，不告诉 LLM 怎么因此改变说话方式
- ExpressionStyleMapper：12 种情绪 → 6 维表达风格覆盖(volume/emoji/sentence/punctuation/tone)
- 每种情绪定义基础指令 + 强烈模式(intense_instructions)两档
- 性格调节：高神经质放大表达、高宜人性缓和负面、高外向增强正面
- 双情绪融合：主+次要情绪按权重叠加
- EmotionalState.to_expression_prompt() + PersonaProfile.build_system_prompt() 自动集成
- chat 端点：每次对话自动计算 expression_style_context 并注入 prompt
- 前端 PersonaCard 新增表达风格指示器面板（4 维度网格+指令预览）
- API: GET /persona/expression-style
- **最终: 422 passed, 0 failed**（+32 新测试，零回归）
- 注意：Python 文件中不能用中文省略号 `…` 和中文引号嵌套，必须用 ASCII 替代

## 数字人控制台（apps/desktop）

- 技术栈：React + TypeScript + 纯 CSS（无 Tailwind）
- 项目结构：App.tsx + ChatPanel / GoalsPanel / StatusPanel / WorldPanel / AutobioPanel

### 2026-04-05 UI 重构完成

**已解决的问题：**
- ✅ 色调从暖棕米色改为深色仪表盘风格（深蓝灰底 + 蓝色/绿色状态指示）
- ✅ 聊天输入改为 textarea，支持 Enter 发送、Shift+Enter 换行
- ✅ 状态 badge 增加颜色语义（推进中-蓝、已暂停-黄、已完成-绿、已放弃-红）
- ✅ 路由切换改为 Tab 导航（总览/对话）
- ✅ 聊天增加 AI 思考 loading 气泡（三点动画）
- ✅ "放弃"和"完成"目标增加确认弹窗
- ✅ 精简顶部条，移除重复信息
- ✅ 标题改用无衬线字体，符合仪表盘风格

**2026-04-05 看板样式优化：**
- ✅ 看板列间距更紧凑（gap 从 16px 减到 12px）
- ✅ 列标题增加分隔线，样式更统一
- ✅ 卡片内边距减小，更紧凑
- ✅ 元数据标签改为小标签样式（链/G0/G1）
- ✅ 移除已收束目标的冗余操作按钮区域
- ✅ 空状态增加虚线边框样式
- ✅ 每列限制最大高度 500px，超出可滚动
- ✅ 列标题可点击折叠/展开
- ✅ 细滚动条样式（4px 宽度）
- ✅ 看板改为 2-1 布局：当前推进 2/3 + 等待恢复 1/3，已收束全宽默认折叠

**2026-04-05 中间区域布局优化（方案 A）：**
- ✅ Inspector Grid 改为 2-1 布局：StatusPanel 占 2/3，WorldPanel 占 1/3
- ✅ AutobioPanel 移至底部全宽显示
- ✅ 自我叙事列表限制最大高度 300px，超出可滚动

**2026-04-05 聊天页面优化：**
- ✅ 侧边栏缩窄至 240px
- ✅ 移除重复状态信息（运行状态、当前阶段）
- ✅ 新增当前目标卡片（带进度条）
- ✅ 新增今日计划步骤列表
- ✅ 新增快捷操作按钮（制定计划、总结对话）
- ✅ 快捷按钮可自动填充输入框

**2026-04-05 聊天界面 macOS iMessage 风格：**
- ✅ 侧边栏移到左侧，主聊天区域在右侧
- ✅ 用户消息靠右显示，使用 iMessage 蓝色渐变 (#007AFF → #0051D5)
- ✅ AI 消息靠左显示，使用灰色气泡
- ✅ 移除消息气泡内的说话人标签（"你"/"小晏"）
- ✅ 圆角气泡样式（18px 圆角，尾巴圆角 4px）
- ✅ 气泡最大宽度 70%，更紧凑的间距

**2026-04-05 WorkBuddy 风格布局重构：**
- ✅ 整体改为左侧边栏 + 右侧主内容区布局
- ✅ 左侧边栏 220px 宽度，包含 Logo、导航、控制按钮
- ✅ 导航项：总览、对话
- ✅ 控制区：唤醒/休眠按钮
- ✅ 底部状态指示器
- ✅ 聊天页面顶部显示当前目标标题
- ✅ 聊天页面显示今日计划进度
- ✅ 输入框底部固定，集成发送按钮
- ✅ 空状态显示快捷操作按钮
- ✅ 保持深色主题色不变

**2026-04-05 设置页面：**
- ✅ 点击侧边栏"数字人"品牌进入设置页面
- ✅ 支持主题切换（深色/浅色，浅色预留）
- ✅ 预留位置：通知、快捷键、数据与隐私
- ✅ 关于信息展示版本号

**设计系统：**
- 深色主题：bg-canvas #0a0f1a, bg-surface #111827
- 语义颜色：primary #3b82f6, success #10b981, warning #f59e0b, danger #ef4444
- 组件化 CSS：btn, panel, status-badge, nav-tab, chat-bubble, goal-board 等
