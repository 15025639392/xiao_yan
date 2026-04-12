import type { SessionHistoryFilter, SessionHubViewModel } from "../../lib/orchestratorWorkbench";

type SessionHistoryPanelProps = {
  viewModel: SessionHubViewModel;
  filter: SessionHistoryFilter;
  activeSessionId: string | null;
  onFilterChange: (next: SessionHistoryFilter) => void;
  onApplyFilter: (next: SessionHistoryFilter) => Promise<void> | void;
  onActivateSession: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void> | void;
};

const STATUS_OPTIONS: Array<{ value: SessionHistoryFilter["status"][number]; label: string }> = [
  { value: "running", label: "运行中" },
  { value: "dispatching", label: "待派发" },
  { value: "pending_plan_approval", label: "待审批" },
  { value: "failed", label: "失败" },
  { value: "completed", label: "完成" },
  { value: "cancelled", label: "取消" },
];

export function SessionHistoryPanel({
  viewModel,
  filter,
  activeSessionId,
  onFilterChange,
  onApplyFilter,
  onActivateSession,
  onResumeSession,
  onDeleteSession,
}: SessionHistoryPanelProps) {
  return (
    <section className="orchestrator-side-section">
      <div className="orchestrator-history-filters" aria-label="会话历史筛选">
        <div className="orchestrator-history-filter-grid">
          <input
            className="chat-page__textarea orchestrator-history-filter-input"
            value={filter.keyword}
            placeholder="关键词或项目名"
            onChange={(event) => onFilterChange({ ...filter, keyword: event.target.value })}
          />
        </div>

        <div className="orchestrator-history-status-row">
          {STATUS_OPTIONS.map((option) => {
            const checked = filter.status.includes(option.value);
            return (
              <label key={option.value} className="orchestrator-history-status-chip">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const nextStatus = checked
                      ? filter.status.filter((item) => item !== option.value)
                      : [...filter.status, option.value];
                    onFilterChange({ ...filter, status: nextStatus });
                  }}
                />
                <span>{option.label}</span>
              </label>
            );
          })}
          <button className="btn btn--secondary btn--sm" type="button" onClick={() => void onApplyFilter(filter)}>
            筛选
          </button>
        </div>
      </div>

      <div className="orchestrator-session-pills" aria-label="历史会话状态分布">
        <span className="orchestrator-pill">运行中 {viewModel.byStatusCount.running}</span>
        <span className="orchestrator-pill">失败 {viewModel.byStatusCount.failed}</span>
        <span className="orchestrator-pill">完成 {viewModel.byStatusCount.completed}</span>
      </div>

      <ul className="orchestrator-session-list">
        {viewModel.sessions.map((item) => {
          const canResume = item.status === "failed" || item.status === "cancelled";
          return (
            <li key={item.session_id}>
              <div className={`orchestrator-session-card ${item.session_id === activeSessionId ? "orchestrator-session-card--active" : ""}`}>
                <div className="orchestrator-session-card__top">
                  <strong>{item.project_name}</strong>
                  <span className={`orchestrator-pill orchestrator-pill--${item.status}`}>{renderSessionStatus(item.status)}</span>
                </div>
                <p>{item.goal}</p>
                <div className="orchestrator-session-card__meta">
                  <span>{new Date(item.updated_at).toLocaleString()}</span>
                </div>
                <div className="orchestrator-inline-card__actions">
                  <button className="chat-page__action-btn" type="button" onClick={() => void onActivateSession(item.session_id)}>
                    恢复会话
                  </button>
                  {canResume ? (
                    <button className="chat-page__action-btn" type="button" onClick={() => void onResumeSession(item.session_id)}>
                      重启推进
                    </button>
                  ) : null}
                  <button className="chat-page__action-btn" type="button" onClick={() => void onDeleteSession(item.session_id)}>
                    删除会话
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function renderSessionStatus(status: SessionHubViewModel["sessions"][number]["status"]): string {
  if (status === "pending_plan_approval") return "待审批";
  if (status === "dispatching") return "待派发";
  if (status === "running") return "运行中";
  if (status === "verifying") return "验收中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  if (status === "planning") return "规划中";
  return "草稿";
}
