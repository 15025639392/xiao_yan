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

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const unit = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const index = Math.floor(Math.log(bytes) / Math.log(unit));
  return parseFloat((bytes / Math.pow(unit, index)).toFixed(1)) + " " + sizes[index];
}

