import { useState } from "react";
import {
  approveStartSelfProgrammingJob,
  delegateSelfProgrammingJob,
  rejectStartSelfProgrammingJob,
  requestStartSelfProgrammingJob,
  type SelfProgrammingJob,
} from "../lib/api";
import { Button, StatusBadge, Textarea } from "./ui";

type StartApprovalPanelProps = {
  job: NonNullable<SelfProgrammingJob>;
  onDecision: (jobId: string) => void;
};

export function StartApprovalPanel({ job, onDecision }: StartApprovalPanelProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
      onDecision(job.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="approval-panel">
      <div className="approval-panel__header">
        <span className="approval-panel__icon">🚦</span>
        <div>
          <h3 className="approval-panel__title">开工审批</h3>
          <p className="approval-panel__subtitle">人工确认后才允许委托 Codex 执行</p>
        </div>
        <StatusBadge tone="active">{job.status}</StatusBadge>
      </div>

      <div className="approval-panel__body">
        <p><strong>理由：</strong>{job.reason_statement ?? job.reason}</p>
        <p><strong>方向：</strong>{job.direction_statement ?? job.spec}</p>

        {job.status === "drafted" ? (
          <Button
            type="button"
            variant="default"
            disabled={busy}
            onClick={() => run(() => requestStartSelfProgrammingJob(job.id))}
          >
            提交开工申请
          </Button>
        ) : null}

        {job.status === "pending_start_approval" ? (
          <div style={{ display: "grid", gap: "var(--space-2)" }}>
            <Button
              type="button"
              variant="default"
              disabled={busy}
              onClick={() => run(() => approveStartSelfProgrammingJob(job.id, "人工确认开工"))}
            >
              确认开工
            </Button>
            <Textarea
              className="approval-reject-form__textarea"
              placeholder="填写拒绝开工原因（可选）"
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => run(() => rejectStartSelfProgrammingJob(job.id, rejectReason || "人工拒绝开工"))}
            >
              拒绝开工
            </Button>
          </div>
        ) : null}

        {job.status === "queued" ? (
          <Button
            type="button"
            variant="default"
            disabled={busy}
            onClick={() => run(() => delegateSelfProgrammingJob(job.id, "codex"))}
          >
            委托 Codex 执行
          </Button>
        ) : null}

        {error ? <div className="approval-error">{error}</div> : null}
      </div>
    </section>
  );
}
