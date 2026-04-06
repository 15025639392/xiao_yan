import type { SelfProgrammingJobState } from "./selfProgrammingTypes";

type SelfProgrammingGitSectionProps = {
  job: SelfProgrammingJobState;
};

export function SelfProgrammingGitSection({ job }: SelfProgrammingGitSectionProps) {
  if (!job.branch_name && !job.commit_hash && !job.commit_message) {
    return null;
  }

  return (
    <div className="si-section si-section--git">
      <h4 className="si-section__title si-section__title--icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="18" cy="18" r="3" />
          <circle cx="6" cy="6" r="3" />
          <path d="M13 6h3a2 2 0 0 1 2 2v7" />
        </svg>
        Git 工作流
      </h4>
      <div className="si-git-info">
        {job.branch_name ? (
          <div className="si-git-row">
            <span className="si-git-label">分支</span>
            <code className="si-git-value">{job.branch_name}</code>
          </div>
        ) : null}
        {job.commit_hash ? (
          <div className="si-git-row">
            <span className="si-git-label">Commit</span>
            <code className="si-git-value">{job.commit_hash.slice(0, 8)}</code>
          </div>
        ) : null}
        {job.commit_message ? (
          <div className="si-git-row si-git-row--full">
            <span className="si-git-label">Message</span>
            <code className="si-git-value">{job.commit_message}</code>
          </div>
        ) : null}
      </div>
    </div>
  );
}
