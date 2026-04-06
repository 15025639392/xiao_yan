export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    info: "ℹ️",
    filesystem: "📂",
    dev: "💻",
    system: "⚙️",
    network: "🌐",
  };
  return icons[category] || "🔧";
}

export function getCategoryName(category: string): string {
  const names: Record<string, string> = {
    info: "信息查询",
    filesystem: "文件系统",
    dev: "开发工具",
    system: "系统操作",
    network: "网络工具",
  };
  return names[category] || category;
}
