# 项目长期记忆

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

**设计系统：**
- 深色主题：bg-canvas #0a0f1a, bg-surface #111827
- 语义颜色：primary #3b82f6, success #10b981, warning #f59e0b, danger #ef4444
- 组件化 CSS：btn, panel, status-badge, nav-tab, chat-bubble, goal-board 等
