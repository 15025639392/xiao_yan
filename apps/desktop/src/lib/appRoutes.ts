export type AppRoute =
  | "chat"
  | "creative-writing"
  | "upgrade-proposals"
  | "xiaohongshu"
  | "persona"
  | "memory"
  | "tools";

export function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/creative-writing") return "creative-writing";
  if (hash === "#/upgrade-proposals") return "upgrade-proposals";
  if (hash === "#/xiaohongshu") return "xiaohongshu";
  if (hash === "#/persona") return "persona";
  if (hash === "#/memory") return "memory";
  if (hash === "#/history") return "chat";
  if (hash === "#/tools") return "tools";
  return "chat";
}

export function normalizeLegacyHash(hash: string): string {
  if (hash === "#/history" || hash === "#/orchestrator") {
    return routeToHash("chat");
  }
  if (hash === "#/capabilities") {
    return routeToHash("tools");
  }
  return hash;
}

export function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "creative-writing") return "#/creative-writing";
  if (route === "upgrade-proposals") return "#/upgrade-proposals";
  if (route === "xiaohongshu") return "#/xiaohongshu";
  if (route === "persona") return "#/persona";
  if (route === "memory") return "#/memory";
  if (route === "tools") return "#/tools";
}
