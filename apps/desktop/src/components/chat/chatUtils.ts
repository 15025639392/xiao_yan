export function getKindLabel(kind: string): string {
  const map: Record<string, string> = {
    fact: "事实",
    episodic: "事件",
    semantic: "语义",
    emotional: "情感",
    chat_raw: "对话",
  };
  return map[kind] || kind;
}

export function getStrengthLabel(strength: string): string {
  const map: Record<string, string> = {
    faint: "微弱",
    weak: "薄弱",
    normal: "普通",
    vivid: "清晰",
    core: "核心",
  };
  return map[strength] || strength;
}

export function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString("zh-CN");
}

