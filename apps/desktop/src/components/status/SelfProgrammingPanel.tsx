import { useState } from "react";
import { rollbackSelfProgrammingJob } from "../../lib/api";
import { CooldownTimer } from "./CooldownTimer";
import { SelfProgrammingEditsSection } from "./SelfProgrammingEditsSection";
import { SelfProgrammingFilesSection } from "./SelfProgrammingFilesSection";
import { SelfProgrammingGitSection } from "./SelfProgrammingGitSection";
import { SelfProgrammingHeader } from "./SelfProgrammingHeader";
import { SelfProgrammingRollbackModal } from "./SelfProgrammingRollbackModal";
import { SelfProgrammingRollbackSection } from "./SelfProgrammingRollbackSection";
import { SelfProgrammingSafetySection } from "./SelfProgrammingSafetySection";
import { SelfProgrammingSummarySection } from "./SelfProgrammingSummarySection";
import type { SelfProgrammingJobState } from "./selfProgrammingTypes";

type SelfProgrammingPanelProps = {
  job: SelfProgrammingJobState;
  onRollback?: (jobId: string) => void;
};

export function SelfProgrammingPanel({ job, onRollback }: SelfProgrammingPanelProps) {
  const [showDiff, setShowDiff] = useState(false);
  const [showDetails, setShowDetails] = useState(true);
  const [rollingBack, setRollingBack] = useState(false);
  const [rollbackOk, setRollbackOk] = useState<string | null>(null);
  const [rollbackErr, setRollbackErr] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const canRollback = job.status === "applied" && !!job.snapshot_taken;
  const edits = job.edits ?? [];

  async function executeRollback() {
    if (!canRollback) return;
    setShowConfirm(false);
    setRollingBack(true);
    setRollbackOk(null);
    setRollbackErr(null);

    try {
      const result = await rollbackSelfProgrammingJob(job.id, "用户手动触发回滚");
      setRollbackOk(result.message ?? "回滚成功");
      onRollback?.(job.id);
    } catch (error) {
      setRollbackErr(error instanceof Error ? error.message : "回滚失败");
    } finally {
      setRollingBack(false);
    }
  }

  return (
    <section className="si-panel" style={{ marginTop: "var(--space-5)" }}>
      <SelfProgrammingHeader job={job} showDetails={showDetails} onToggle={() => setShowDetails(!showDetails)} />

      {showDetails ? (
        <div className="si-panel__body">
          <SelfProgrammingSummarySection job={job} />
          <SelfProgrammingFilesSection touchedFiles={job.touched_files} />
          <SelfProgrammingGitSection job={job} />
          <SelfProgrammingSafetySection job={job} />
          <SelfProgrammingEditsSection edits={edits} showDiff={showDiff} onToggle={() => setShowDiff(!showDiff)} />
          <SelfProgrammingRollbackSection
            canRollback={canRollback}
            rollbackInfo={job.rollback_info}
            rollingBack={rollingBack}
            rollbackOk={rollbackOk}
            rollbackErr={rollbackErr}
            onOpenConfirm={() => setShowConfirm(true)}
          />
          {job.cooldown_until ? <CooldownTimer until={job.cooldown_until} /> : null}
        </div>
      ) : null}

      {showConfirm ? (
        <SelfProgrammingRollbackModal
          touchedFiles={job.touched_files ?? []}
          rollingBack={rollingBack}
          onCancel={() => setShowConfirm(false)}
          onConfirm={executeRollback}
        />
      ) : null}
    </section>
  );
}
