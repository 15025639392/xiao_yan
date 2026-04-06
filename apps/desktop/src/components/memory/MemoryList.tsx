import type { MemoryEntryDisplay } from "../../lib/api";
import type { ViewMode } from "./memoryConstants";
import { THEME_CLUSTERS } from "./memoryConstants";
import { groupEntriesByDate, groupEntriesByTheme } from "./memoryUtils";

type MemoryListProps = {
  loading: boolean;
  entries: MemoryEntryDisplay[];
  viewMode: ViewMode;
  renderItem: (entry: MemoryEntryDisplay) => JSX.Element;
};

export function MemoryList({ loading, entries, viewMode, renderItem }: MemoryListProps) {
  if (loading) {
    return (
      <div className="memory-list__skeleton">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="memory-skeleton-item">
            <div className="memory-skeleton-icon" />
            <div className="memory-skeleton-content">
              <div className="memory-skeleton-line memory-skeleton-line--long" />
              <div className="memory-skeleton-line memory-skeleton-line--short" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="memory-list__empty">
        <span className="memory-list__empty-icon">🌀</span>
        <p>还没有记忆</p>
        <span className="memory-list__empty-hint">开始对话后会自动记录</span>
      </div>
    );
  }

  return (
    <>
      {viewMode === "timeline"
        ? groupEntriesByDate(entries).map(([dateGroup, groupEntries]) => (
            <div key={dateGroup} className="memory-group">
              <div className="memory-group__header">
                <span className="memory-group__label">{dateGroup}</span>
                <span className="memory-group__count">{groupEntries.length} 条</span>
              </div>
              <div className="memory-group__items">{groupEntries.map(renderItem)}</div>
            </div>
          ))
        : groupEntriesByTheme(entries).map(([clusterId, clusterEntries]) => {
            const clusterConfig = THEME_CLUSTERS[clusterId];
            return (
              <div key={clusterId} className="memory-cluster">
                <div className="memory-cluster__header">
                  <span className="memory-cluster__icon">{clusterConfig.icon}</span>
                  <span className="memory-cluster__label">{clusterConfig.label}</span>
                  <span className="memory-cluster__count">{clusterEntries.length} 条</span>
                </div>
                <div className="memory-cluster__items">{clusterEntries.map(renderItem)}</div>
              </div>
            );
          })}
    </>
  );
}

