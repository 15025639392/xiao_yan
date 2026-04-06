import { useState } from "react";
import { approveSelfProgrammingJob, rejectSelfProgrammingJob, type SelfProgrammingJob } from "../lib/api";
import { ApprovalActions } from "./approval/ApprovalActions";
import { ApprovalEditsSection } from "./approval/ApprovalEditsSection";
import { ApprovalResult } from "./approval/ApprovalResult";
import { ApprovalSummary } from "./approval/ApprovalSummary";
import { StatusBadge } from "./ui";

type ApprovalPanelProps = {
  job: NonNullable<SelfProgrammingJob>;
  onDecision: (jobId: string, approved: boolean) => void;
};

export function ApprovalPanel({ job, onDecision }: ApprovalPanelProps) {
  const [decisioning, setDecisioning] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [result, setResult] = useState<"approved" | "rejected" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEdits, setShowEdits] = useState(false);

  const edits = job.edits ?? [];

  async function handleApprove() {
    if (decisioning) return;
    setDecisioning(true);
    setError(null);
    try {
      await approveSelfProgrammingJob(job.id);
      setResult("approved");
      onDecision(job.id, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "审批失败");
    } finally {
      setDecisioning(false);
    }
  }

  async function handleReject() {
    if (!rejectReason.trim()) {
      setError("请填写拒绝原因");
      return;
    }
    if (decisioning) return;
    setDecisioning(true);
    setError(null);
    try {
      await rejectSelfProgrammingJob(job.id, rejectReason.trim());
      setResult("rejected");
      onDecision(job.id, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setDecisioning(false);
    }
  }

  if (result) {
    return (
      <ApprovalResult
        result={result}
        targetArea={job.target_area}
        rejectReason={rejectReason}
        approvalReason={job.approval_reason}
      />
    );
  }

  return (
    <section className="approval-panel">
      <div className="approval-panel__header">
        <span className="approval-panel__icon">🔔</span>
        <div>
          <h3 className="approval-panel__title">等待审批</h3>
          <p className="approval-panel__subtitle">数字人已完成补丁编写，等待你确认是否应用</p>
        </div>
        <StatusBadge tone="active">待审批</StatusBadge>
      </div>

      <div className="approval-panel__body">
        <ApprovalSummary job={job} />
        <ApprovalEditsSection edits={edits} showEdits={showEdits} onToggle={() => setShowEdits(!showEdits)} />
        {error ? <div className="approval-error">{error}</div> : null}
        <ApprovalActions
          showRejectForm={showRejectForm}
          decisioning={decisioning}
          rejectReason={rejectReason}
          onApprove={handleApprove}
          onOpenRejectForm={() => setShowRejectForm(true)}
          onRejectReasonChange={setRejectReason}
          onCancelReject={() => {
            setShowRejectForm(false);
            setRejectReason("");
          }}
          onReject={handleReject}
        />
      </div>
    </section>
  );
}
