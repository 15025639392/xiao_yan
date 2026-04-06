import { StatusBadge } from "../ui";
import { HealthRing } from "./HealthRing";
import type { SelfProgrammingJobState } from "./selfProgrammingTypes";
import { renderSelfProgrammingStatus, siStatusClass } from "./statusUtils";

type SelfProgrammingHeaderProps = {
  job: SelfProgrammingJobState;
  showDetails: boolean;
  onToggle: () => void;
};

export function SelfProgrammingHeader({ job, showDetails, onToggle }: SelfProgrammingHeaderProps) {
  const hasHealthData = job.health_score != null;

  return (
    <div className="si-panel__header" onClick={onToggle} style={{ cursor: "pointer" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span className="si-panel__icon">🧬</span>
        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>自我编程</h3>
        {job.candidate_label ? <span className="si-badge si-badge--candidate">{job.candidate_label}</span> : null}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        {hasHealthData ? <HealthRing score={job.health_score!} grade={job.health_grade!} /> : null}
        <StatusBadge tone={siStatusClass(job.status)}>{renderSelfProgrammingStatus(job.status)}</StatusBadge>
        <svg
          className="si-chevron"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          width="16"
          height="16"
          style={{
            transform: showDetails ? "rotate(180deg)" : "rotate(0)",
            transition: "transform 200ms ease",
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>
  );
}
