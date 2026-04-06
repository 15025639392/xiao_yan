import type { ToolsStatusResponse } from "../../lib/api";

type StatusTabProps = {
  status: ToolsStatusResponse | null;
  onRefresh?: () => void;
};

export function StatusTab({ status, onRefresh }: StatusTabProps) {
  if (!status) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>;
  }

  const stats = status.statistics;
  const rateColor =
    stats.success_rate >= 0.8
      ? "var(--success)"
      : stats.success_rate >= 0.5
        ? "var(--warning)"
        : "var(--danger)";

  return (
    <div className="status-tab">
      <div className="status-grid">
        <div className="status-metric">
          <p className="status-metric__value">{stats.total_executions}</p>
          <p className="status-metric__label">总执行次数</p>
        </div>
        <div className="status-metric">
          <p className="status-metric__value" style={{ color: rateColor }}>
            {Math.round(stats.success_rate * 100)}%
          </p>
          <p className="status-metric__label">成功率</p>
        </div>
        <div className="status-metric">
          <p
            className="status-metric__value"
            style={{ color: stats.failed_count > 0 ? "var(--danger)" : undefined }}
          >
            {stats.failed_count}
          </p>
          <p className="status-metric__label">失败</p>
        </div>
        <div className="status-metric">
          <p
            className="status-metric__value"
            style={{ color: stats.timeout_count > 0 ? "var(--warning)" : undefined }}
          >
            {stats.timeout_count}
          </p>
          <p className="status-metric__label">超时</p>
        </div>
      </div>

      <div className="status-config">
        <h4>配置</h4>
        <dl className="status-dl">
          <dt>安全级别</dt>
          <dd>{status.safety_filter}</dd>
          <dt>可用命令数</dt>
          <dd>{status.allowed_command_count} 个</dd>
          <dt>工作目录</dt>
          <dd>
            <code>{status.working_directory}</code>
          </dd>
          <dt>超时限制</dt>
          <dd>{status.timeout_seconds}s</dd>
          <dt>沙箱</dt>
          <dd>{status.sandbox_enabled ? "已启用" : "未启用"}</dd>
          <dt>历史记录</dt>
          <dd>{status.history_size} 条</dd>
        </dl>
      </div>

      {status.recently_used_tools.length > 0 ? (
        <div className="status-recent-tools">
          <h4>最近使用的工具</h4>
          <div className="recent-tools-list">
            {status.recently_used_tools.map(([name, count]) => (
              <div key={name} className="recent-tool-item">
                <code>{name}</code>
                <span className="recent-tool-count">{count} 次</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <button type="button" className="btn btn--sm" onClick={onRefresh} style={{ marginTop: "var(--space-4)" }}>
        🔄 刷新状态
      </button>
    </div>
  );
}

