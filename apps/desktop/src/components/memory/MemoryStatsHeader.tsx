import type { MemorySummary } from "../../lib/api";
import { KIND_LABELS } from "./memoryConstants";

type MemoryStatsHeaderProps = {
  summary: MemorySummary | null;
  activeFilter: string | null;
  onFilterToggle: (kind: string) => void;
};

export function MemoryStatsHeader({ summary, activeFilter, onFilterToggle }: MemoryStatsHeaderProps) {
  if (!summary || !summary.available || Object.keys(summary.by_kind).length === 0) {
    return null;
  }

  return (
    <div className="memory-panel__header">
      <div className="memory-stats">
        {Object.entries(summary.by_kind).map(([kind, count]) => {
          const info = KIND_LABELS[kind];
          if (!info) return null;
          return (
            <button
              key={kind}
              className={`memory-stats__chip ${activeFilter === kind ? "memory-stats__chip--active" : ""}`}
              onClick={() => onFilterToggle(kind)}
              title={info.label}
              type="button"
            >
              <span>{info.icon}</span>
              <span>{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

