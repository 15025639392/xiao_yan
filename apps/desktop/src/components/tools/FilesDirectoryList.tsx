import type { DirectoryEntry } from "../../lib/api";
import { formatBytes } from "../../lib/utils";

type FilesDirectoryListProps = {
  loading: boolean;
  entries: DirectoryEntry[] | null;
  onClickEntry: (entry: DirectoryEntry) => void;
};

export function FilesDirectoryList({ loading, entries, onClickEntry }: FilesDirectoryListProps) {
  return (
    <div className="dir-list">
      {loading ? (
        <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>
      ) : entries ? (
        entries.length > 0 ? (
          entries.map((entry) => (
            <div
              key={`${entry.type}-${entry.path}`}
              className={`dir-entry dir-entry--${entry.type}`}
              onClick={() => onClickEntry(entry)}
            >
              <span className="dir-entry__icon">
                {entry.type === "dir" ? "📁" : entry.type === "symlink" ? "🔗" : "📄"}
              </span>
              <span className="dir-entry__name">{entry.name}</span>
              <span className="dir-entry__size">{entry.type === "file" ? formatBytes(entry.size_bytes) : ""}</span>
            </div>
          ))
        ) : (
          <p style={{ color: "var(--text-tertiary)" }}>空目录</p>
        )
      ) : null}
    </div>
  );
}
