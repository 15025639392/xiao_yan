import type { BeingState } from "../../lib/api";
import { getHealthColor } from "../../lib/utils";

export function renderSelfProgrammingStatus(
  status: NonNullable<BeingState["self_programming_job"]>["status"],
): string {
  const map: Record<string, string> = {
    pending: "待开始",
    diagnosing: "诊断中",
    patching: "修补中",
    pending_approval: "待审批",
    verifying: "验证中",
    applied: "已生效",
    failed: "失败",
    rejected: "已拒绝",
  };
  return map[status] ?? status;
}

export function siStatusClass(status: string): string {
  if (status === "applied") return "completed";
  if (status === "failed") return "abandoned";
  if (status === "rejected") return "abandoned";
  if (status === "pending_approval") return "active";
  if (status === "verifying") return "active";
  if (status === "patching") return "active";
  return "paused";
}

export function conflictIcon(severity: string): string {
  if (severity === "blocking") return "🚫";
  if (severity === "warning") return "⚠️";
  return "✅";
}

export function conflictLabel(severity: string): string {
  if (severity === "blocking") return "阻断冲突";
  if (severity === "warning") return "警告";
  return "安全";
}

export function healthColor(score: number): string {
  return getHealthColor(score);
}
