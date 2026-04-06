import { formatRelativeTimeZh, lookupOrKey } from "../../lib/utils";

export function getKindLabel(kind: string): string {
  const map: Record<string, string> = {
    fact: "事实",
    episodic: "事件",
    semantic: "语义",
    emotional: "情感",
    chat_raw: "对话",
  };
  return lookupOrKey(map, kind);
}

export function getStrengthLabel(strength: string): string {
  const map: Record<string, string> = {
    faint: "微弱",
    weak: "薄弱",
    normal: "普通",
    vivid: "清晰",
    core: "核心",
  };
  return lookupOrKey(map, strength);
}

export function formatRelativeDate(dateString: string): string {
  return formatRelativeTimeZh(dateString, { maxRelativeDays: 7, dateFallback: "full" });
}
