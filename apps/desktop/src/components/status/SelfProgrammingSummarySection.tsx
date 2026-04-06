import type { SelfProgrammingJobState } from "./selfProgrammingTypes";
import { renderSelfProgrammingStatus } from "./statusUtils";

type SelfProgrammingSummarySectionProps = {
  job: SelfProgrammingJobState;
};

export function SelfProgrammingSummarySection({ job }: SelfProgrammingSummarySectionProps) {
  return (
    <>
      <div className="si-grid">
        <div className="si-field">
          <span className="si-field__label">目标区域</span>
          <span className="si-field__value">{job.target_area}</span>
        </div>
        <div className="si-field">
          <span className="si-field__label">阶段</span>
          <span className="si-field__value si-field__value--phase">{renderSelfProgrammingStatus(job.status)}</span>
        </div>
      </div>

      <div className="si-section">
        <div className="si-section__row">
          <div className="si-section__col">
            <h4 className="si-section__title">原因</h4>
            <p className="si-section__text">{job.reason}</p>
          </div>
          <div className="si-section__col">
            <h4 className="si-section__title">方案</h4>
            <p className="si-section__text">{job.spec}</p>
          </div>
        </div>
      </div>

      {job.patch_summary ? (
        <div className="si-section">
          <h4 className="si-section__title">补丁摘要</h4>
          <p className="si-section__text si-text--mono">{job.patch_summary}</p>
        </div>
      ) : null}
    </>
  );
}
