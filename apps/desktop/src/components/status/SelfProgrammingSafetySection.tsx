import type { SelfProgrammingJobState } from "./selfProgrammingTypes";
import { conflictIcon, conflictLabel } from "./statusUtils";

type SelfProgrammingSafetySectionProps = {
  job: SelfProgrammingJobState;
};

export function SelfProgrammingSafetySection({ job }: SelfProgrammingSafetySectionProps) {
  if (!job.sandbox_prechecked && job.conflict_severity === "safe") {
    return null;
  }

  const severity = job.conflict_severity ?? "safe";

  return (
    <div className="si-section">
      <h4 className="si-section__title si-section__title--icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        安全检查
      </h4>
      <div className="si-safety-grid">
        {job.sandbox_prechecked ? (
          <div className={`si-safety-item ${job.sandbox_result ? "si-safety-item--ok" : ""}`}>
            <span className="si-safety-icon">🛡️</span>
            <div>
              <span className="si-safety-label">沙箱预检</span>
              <span className="si-safety-detail">{job.sandbox_result ?? "通过"}</span>
            </div>
          </div>
        ) : null}
        <div className={`si-safety-item si-safety-item--${severity}`}>
          <span className="si-safety-icon">{conflictIcon(severity)}</span>
          <div>
            <span className="si-safety-label">冲突检测</span>
            <span className="si-safety-detail">{conflictLabel(severity)}</span>
          </div>
        </div>
      </div>
      {job.conflict_details ? <p className="si-conflict-detail">{job.conflict_details}</p> : null}
    </div>
  );
}
