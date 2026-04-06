import { useState, useEffect } from "react";
import type { SelfProgrammingHistoryEntry } from "../lib/api";
import { getHealthColor } from "../lib/utils";
import { formatDuration, formatRelativeTime } from "./history/historyUtils";
import { renderSelfProgrammingStatus, siStatusClass } from "./status/statusUtils";
import { Panel, StatusBadge } from "./ui";

export type { SelfProgrammingHistoryEntry };
import { fetchSelfProgrammingHistory } from "../lib/api";

type HistoryPanelProps = {
  /** 是否可见 */
  visible?: boolean;
  /** 点击历史项时的回调（可选，用于查看详情） */
  onSelectEntry?: (entry: SelfProgrammingHistoryEntry) => void;
};

export function HistoryPanel({ visible = true, onSelectEntry }: HistoryPanelProps) {
  const [entries, setEntries] = useState<SelfProgrammingHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchSelfProgrammingHistory();
        if (!cancelled) {
          setEntries(res.entries ?? []);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
  }, [visible]);

  if (!visible) return null;

  return (
    <Panel
      className="history-panel"
      icon="📜"
      title="自我编程历史"
      subtitle="所有自我编程操作记录"
      actions={<span className="history-count">{entries.length} 条记录</span>}
    >
      {loading && entries.length === 0 ? (
        <div className="history-loading">
          <span className="history-loading__spinner" />
          加载中...
        </div>
      ) : error ? (
        <div className="history-error">{error}</div>
      ) : entries.length === 0 ? (
        <div className="history-empty">
          <span className="history-empty__icon">🧬</span>
          <p>还没有自我编程历史记录</p>
          <span className="history-empty__hint">当数字人进行自我编程时，记录会出现在这里</span>
        </div>
      ) : (
        <ul className="history-list">
          {entries.map((entry) => (
            <li
              key={entry.job_id}
              className={`history-item history-item--${entry.status}`}
              onClick={() => onSelectEntry?.(entry)}
            >
              {/* 头部：时间 + 状态 */}
              <div className="history-item__header">
                <time className="history-item__time" dateTime={entry.created_at}>
                  {formatRelativeTime(entry.created_at)}
                </time>
                <StatusBadge tone={siStatusClass(entry.status)}>
                  {renderSelfProgrammingStatus(entry.status)}
                </StatusBadge>
                {entry.had_rollback ? (
                  <span className="history-badge--rolledback" title="已回滚">↩️</span>
                ) : null}
              </div>

              {/* 核心信息 */}
              <div className="history-item__body">
                <h4 className="history-item__area">{entry.target_area}</h4>
                <p className="history-item__reason">{entry.reason}</p>
              </div>

              {/* 元数据行 */}
              <div className="history-item__meta">
                {entry.touched_files.length > 0 ? (
                  <span className="history-meta__files" title={entry.touched_files.join(", ")}>
                    📄 {entry.touched_files.length} 文件
                  </span>
                ) : null}

                {entry.health_score != null ? (
                  <span
                    className="history-meta__health"
                    style={{ color: getHealthColor(entry.health_score) }}
                    title={`健康度 ${entry.health_score.toFixed(0)} 分`}
                  >
                    ♥ {entry.health_score.toFixed(0)}
                  </span>
                ) : null}

                <span className="history-meta__outcome">{entry.outcome}</span>
              </div>

              {/* 完成时间 */}
              {entry.completed_at ? (
                <div className="history-item__duration">
                  持续: {formatDuration(entry.created_at, entry.completed_at)}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
