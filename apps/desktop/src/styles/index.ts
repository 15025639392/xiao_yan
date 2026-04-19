/**
 * CSS 模块统一入口
 * 
 * 加载顺序很重要：变量 → 基础 → 布局 → 组件 → 各页面模块
 * 
 * 模块说明：
 * - variables.css   CSS 自定义属性（暗色/亮色主题）
 * - base.css        Reset / 全局基础样式
 * - layout.css      App 布局 + 侧边栏 + 主内容区 + 导航标签
 * - components.css  按钮 + 面板 + Badge 通用组件
 * - chat/*          聊天页面（消息/气泡/输入框/Markdown）
 * - modal.css       弹窗/对话框
 * - tools.css       工具箱面板（5 Tab）
 * - capabilities.css 能力中枢页面（能力清单/学习进度/审批）
 * - emotion-panel.css 情绪面板
 * - responsive.css  响应式断点
 */

import "./tailwind.css";
import "./variables.css";
import "./base.css";
import "./layout.css";
import "./components.css";
import "./chat/index.css";
import "./modal.css";
import "./tools.css";
import "./capabilities.css";
import "./emotion-panel.css";
import "./responsive.css";
