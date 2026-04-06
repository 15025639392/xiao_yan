export const KIND_LABELS: Record<string, { label: string; icon: string; color: string; bgColor: string }> = {
  fact: { label: "事实", icon: "📌", color: "#3b82f6", bgColor: "rgba(59, 130, 246, 0.1)" },
  episodic: { label: "经历", icon: "💭", color: "#6366f1", bgColor: "rgba(99, 102, 241, 0.1)" },
  semantic: { label: "知识", icon: "📚", color: "#10b981", bgColor: "rgba(16, 185, 129, 0.1)" },
  emotional: { label: "情绪", icon: "💓", color: "#ef4444", bgColor: "rgba(239, 68, 68, 0.1)" },
  chat_raw: { label: "对话", icon: "💬", color: "#9ca3af", bgColor: "rgba(156, 163, 175, 0.1)" },
};

export const STRENGTH_COLORS: Record<string, string> = {
  faint: "rgba(255, 255, 255, 0.1)",
  weak: "rgba(255, 255, 255, 0.2)",
  normal: "rgba(245, 158, 11, 0.4)",
  vivid: "rgba(59, 130, 246, 0.5)",
  core: "rgba(245, 158, 11, 0.8)",
};

export const ROLE_LABELS: Record<string, string> = {
  user: "你",
  system: "系统",
};

export type ViewMode = "timeline" | "cluster";

export const THEME_CLUSTERS: Record<string, { label: string; icon: string; keywords: string[] }> = {
  about_user: {
    label: "关于你",
    icon: "👤",
    keywords: ["喜欢", "爱", "讨厌", "名字", "叫", "我是", "我的工作", "我的职业", "我从事", "我的家乡", "我来自"],
  },
  preferences: {
    label: "偏好习惯",
    icon: "⚙️",
    keywords: ["习惯", "偏好", "通常", "经常", "总是", "从不", "喜欢", "不喜欢"],
  },
  schedule: {
    label: "日程待办",
    icon: "📅",
    keywords: ["明天", "后天", "下周", "记得", "提醒", "会议", "约会", "截止", "交", "完成"],
  },
  knowledge: {
    label: "知识观点",
    icon: "💡",
    keywords: ["认为", "觉得", "观点是", "知识", "知道", "了解", "学习"],
  },
  emotions: {
    label: "情绪感受",
    icon: "🎭",
    keywords: ["开心", "难过", "累", "焦虑", "兴奋", "担心", "感觉", "心情"],
  },
  chat: {
    label: "闲聊对话",
    icon: "💬",
    keywords: [],
  },
};

