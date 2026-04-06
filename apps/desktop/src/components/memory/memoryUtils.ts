import type { MemoryEntryDisplay } from "../../lib/api";
import { formatRelativeTimeZh, lookupOrKey } from "../../lib/utils";
import { ROLE_LABELS, THEME_CLUSTERS } from "./memoryConstants";

export function formatRelativeTime(isoStr: string | null): string {
  return formatRelativeTimeZh(isoStr, { maxRelativeDays: 7, dateFallback: "short" });
}

function getDateGroup(isoStr: string | null): string {
  if (!isoStr) return "更早";
  const d = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDay = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDay === 0) return "今天";
  if (diffDay === 1) return "昨天";
  if (diffDay < 7) return "本周";
  if (diffDay < 30) return "本月";
  return "更早";
}

export function groupEntriesByDate(entries: MemoryEntryDisplay[]): [string, MemoryEntryDisplay[]][] {
  const groups = new Map<string, MemoryEntryDisplay[]>();

  entries.forEach((entry) => {
    const group = getDateGroup(entry.created_at);
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push(entry);
  });

  const groupOrder = ["今天", "昨天", "本周", "本月", "更早"];
  return groupOrder.filter((g) => groups.has(g)).map((g) => [g, groups.get(g)!] as [string, MemoryEntryDisplay[]]);
}

function getThemeCluster(entry: MemoryEntryDisplay): string {
  const text = (entry.content + " " + entry.keywords.join(" ")).toLowerCase();

  if (entry.kind === "emotional") return "emotions";

  for (const [clusterId, config] of Object.entries(THEME_CLUSTERS)) {
    if (clusterId === "chat") continue;
    for (const keyword of config.keywords) {
      if (text.includes(keyword.toLowerCase())) {
        return clusterId;
      }
    }
  }

  return "chat";
}

export function groupEntriesByTheme(entries: MemoryEntryDisplay[]): [string, MemoryEntryDisplay[]][] {
  const groups = new Map<string, MemoryEntryDisplay[]>();

  entries.forEach((entry) => {
    const cluster = getThemeCluster(entry);
    if (!groups.has(cluster)) {
      groups.set(cluster, []);
    }
    groups.get(cluster)!.push(entry);
  });

  const clusterOrder = ["about_user", "schedule", "preferences", "emotions", "knowledge", "chat"];
  return clusterOrder
    .filter((c) => groups.has(c) && groups.get(c)!.length > 0)
    .map((c) => [c, groups.get(c)!] as [string, MemoryEntryDisplay[]]);
}

export function roleLabelFor(role: string | null, assistantName: string): string | null {
  if (!role) {
    return null;
  }
  if (role === "assistant") {
    return assistantName;
  }
  return lookupOrKey(ROLE_LABELS, role);
}
