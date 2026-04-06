import { useEffect, useState } from "react";
import type { ToolHistoryEntry } from "../../lib/api";
import { clearToolHistory, fetchToolHistory } from "../../lib/api";

export function HistoryTab() {
  const [history, setHistory] = useState<ToolHistoryEntry[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchToolHistory(50)
      .then((res) => {
        setHistory(res.entries);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  async function handleClear() {
    await clearToolHistory();
    setHistory([]);
  }

  if (!loaded) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载历史...</p>;
  }

  return (
    <div className="history-tab">
      <div className="history-tab__actions">
        <span className="history-count">{history.length} 条记录</span>
        {history.length > 0 ? (
          <button type="button" className="btn btn--sm" onClick={() => void handleClear()}>
            🗑 清空历史
          </button>
        ) : null}
      </div>

      {history.length > 0 ? (
        <div className="history-list">
          {history.map((entry, index) => (
            <div
              key={entry.id || index}
              className={`history-item history-item--${entry.success ? "ok" : "fail"}`}
            >
              <div className="history-item__main">
                <code className="history-item__cmd">{entry.command}</code>
                <span className="history-item__time">{entry.created_at?.slice(11, 19)}</span>
              </div>
              <div className="history-item__meta">
                <span className={`history-badge history-badge--${entry.success ? "ok" : "fail"}`}>
                  {entry.exit_code === -1 ? "ERR" : `exit ${entry.exit_code}`}
                </span>
                <span>{entry.duration_seconds?.toFixed(1) ?? "?"}s</span>
                {entry.tool_name ? <span className="history-tool-name">{entry.tool_name}</span> : null}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: "var(--text-tertiary)", padding: "var(--space-6)", textAlign: "center" }}>暂无执行记录</p>
      )}
    </div>
  );
}

