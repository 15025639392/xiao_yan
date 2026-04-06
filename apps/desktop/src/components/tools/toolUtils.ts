import { lookupOrDefault, lookupOrKey } from "../../lib/utils";

export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    info: "ℹ️",
    filesystem: "📂",
    dev: "💻",
    system: "⚙️",
    network: "🌐",
  };
  return lookupOrDefault(icons, category, "🔧");
}

export function getCategoryName(category: string): string {
  const names: Record<string, string> = {
    info: "信息查询",
    filesystem: "文件系统",
    dev: "开发工具",
    system: "系统操作",
    network: "网络工具",
  };
  return lookupOrKey(names, category);
}

export function getSafetyLevelColor(level: string): string {
  const colors: Record<string, string> = {
    safe: "var(--success)",
    restricted: "var(--info)",
    dangerous: "var(--warning)",
    blocked: "var(--danger)",
  };
  return lookupOrDefault(colors, level, "inherit");
}

export function getSafetyLevelLabel(level: string): string {
  const labels: Record<string, string> = {
    safe: "安全",
    restricted: "受限",
    dangerous: "危险",
    blocked: "禁止",
  };
  return lookupOrKey(labels, level);
}

export function getSuccessRateColor(successRate: number): string {
  if (successRate >= 0.8) return "var(--success)";
  if (successRate >= 0.5) return "var(--warning)";
  return "var(--danger)";
}

export function getSuccessRateBadgeStyle(successRate: number): { background: string; color: string } {
  if (successRate >= 0.8) {
    return { background: "var(--success-muted)", color: getSuccessRateColor(successRate) };
  }
  if (successRate >= 0.5) {
    return { background: "var(--warning-muted)", color: getSuccessRateColor(successRate) };
  }
  return { background: "var(--danger-muted)", color: getSuccessRateColor(successRate) };
}
