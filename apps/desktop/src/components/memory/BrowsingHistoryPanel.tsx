import { useCallback, useEffect, useState } from "react";
import { fetchAutobio } from "../../lib/api";

export type BrowserHistoryEntry = {
  content: string;
  timestamp: string;
};

type BrowsingHistoryPanelProps = {
  className?: string;
};

export function BrowsingHistoryPanel({ className }: BrowsingHistoryPanelProps) {
  const [entries, setEntries] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchAutobio();
      setEntries(data.entries ?? []);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className={`browsing-history-panel ${className ?? ""}`}>
      <div className="browsing-history-panel__header">
        <h3 className="browsing-history-panel__title">🌐 浏览历史</h3>
      </div>
      {loading ? (
        <div className="browsing-history-panel__empty">加载中...</div>
      ) : entries.length === 0 ? (
        <div className="browsing-history-panel__empty">暂无浏览记录</div>
      ) : (
        <ul className="browsing-history-panel__list">
          {entries.map((entry, i) => (
            <li key={i} className="browsing-history-panel__entry">
              <span className="browsing-history-panel__icon">🌐</span>
              <span className="browsing-history-panel__content">{entry}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
