import type { BeingState } from "../../lib/api";
import { lookupOrDefault, lookupOrKey } from "../../lib/utils";

export function renderSelfProgrammingStatus(
  status: NonNullable<BeingState["self_programming_job"]>["status"],
): string {
  const map: Record<string, string> = {
    drafted: "草案",
    pending_start_approval: "待开工审批",
    queued: "已排队",
    running: "执行中",
    completed: "已完成",
    frozen: "已冻结",
    pending: "待开始",
    diagnosing: "诊断中",
    patching: "修补中",
    pending_approval: "待审批",
    verifying: "验证中",
    applied: "已生效",
    failed: "失败",
    rejected: "已拒绝",
  };
  return lookupOrKey(map, status);
}

export function siStatusClass(status: string): string {
  if (status === "applied") return "completed";
  if (status === "completed") return "completed";
  if (status === "failed") return "abandoned";
  if (status === "frozen") return "abandoned";
  if (status === "rejected") return "abandoned";
  if (status === "pending_start_approval") return "active";
  if (status === "queued") return "active";
  if (status === "running") return "active";
  if (status === "drafted") return "paused";
  if (status === "pending_approval") return "active";
  if (status === "verifying") return "active";
  if (status === "patching") return "active";
  return "paused";
}

export function conflictIcon(severity: string): string {
  const map: Record<string, string> = {
    blocking: "🚫",
    warning: "⚠️",
  };
  return lookupOrDefault(map, severity, "✅");
}

export function conflictLabel(severity: string): string {
  const map: Record<string, string> = {
    blocking: "阻断冲突",
    warning: "警告",
  };
  return lookupOrDefault(map, severity, "安全");
}
