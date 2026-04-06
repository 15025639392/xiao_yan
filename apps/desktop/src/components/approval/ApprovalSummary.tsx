import type { SelfProgrammingJob } from "../../lib/api";

type ApprovalSummaryProps = {
  job: NonNullable<SelfProgrammingJob>;
};

export function ApprovalSummary({ job }: ApprovalSummaryProps) {
  return (
    <>
      <div className="approval-summary">
        <div className="approval-summary__row">
          <span className="approval-summary__label">目标区域</span>
          <span className="approval-summary__value">{job.target_area}</span>
        </div>
        <div className="approval-summary__row">
          <span className="approval-summary__label">原因</span>
          <span className="approval-summary__value">{job.reason}</span>
        </div>
        <div className="approval-summary__row">
          <span className="approval-summary__label">方案</span>
          <span className="approval-summary__value">{job.spec}</span>
        </div>
        {job.patch_summary ? (
          <div className="approval-summary__row">
            <span className="approval-summary__label">补丁摘要</span>
            <code className="approval-summary__code">{job.patch_summary}</code>
          </div>
        ) : null}
        {job.approval_edits_summary ? (
          <div className="approval-summary__row">
            <span className="approval-summary__label">编辑内容</span>
            <code className="approval-summary__code">{job.approval_edits_summary}</code>
          </div>
        ) : null}
      </div>

      {job.touched_files && job.touched_files.length > 0 ? (
        <div className="approval-files">
          <h4 className="approval-files__title">将修改 {job.touched_files.length} 个文件：</h4>
          <ul className="approval-files__list">
            {job.touched_files.map((fp) => (
              <li key={fp} className="approval-files__item">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-8V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <code>{fp}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
