export type AppRoute =
  | "overview"
  | "chat"
  | "persona"
  | "memory"
  | "tools"
  | "capabilities";

export function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/persona") return "persona";
  if (hash === "#/memory") return "memory";
  if (hash === "#/history") return "overview";
  if (hash === "#/tools") return "tools";
  if (hash === "#/capabilities") return "capabilities";
  return "overview";
}

export function normalizeLegacyHash(hash: string): string {
  if (hash === "#/history" || hash === "#/orchestrator") {
    return routeToHash("overview");
  }
  return hash;
}

export function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "persona") return "#/persona";
  if (route === "memory") return "#/memory";
  if (route === "tools") return "#/tools";
  if (route === "capabilities") return "#/capabilities";
  return "#/";
}
