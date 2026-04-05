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
 * - chat.css        聊天页面（消息/气泡/输入框/Markdown）
 * - overview.css    总览页面（Inspector/看板/指标卡/叙事）
 * - modal.css       弹窗/对话框
 * - self-programming.css  自我编程面板（候选/Diff/Git/安全检查）
 * - approval.css    审批交互面板
 * - tools.css       工具箱面板（5 Tab）
 * - responsive.css  响应式断点
 */

import "./variables.css";
import "./base.css";
import "./layout.css";
import "./components.css";
import "./chat.css";
import "./overview.css";
import "./modal.css";
import "./self-programming.css";
import "./approval.css";
import "./tools.css";
import "./responsive.css";
