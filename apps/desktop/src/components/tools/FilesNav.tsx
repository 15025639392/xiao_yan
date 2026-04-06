type FilesNavProps = {
  currentPath: string;
  onNavigateUp: () => void;
  onRefresh: () => void;
};

export function FilesNav({ currentPath, onNavigateUp, onRefresh }: FilesNavProps) {
  return (
    <div className="files-nav">
      <button type="button" className="btn btn--sm" onClick={onNavigateUp} disabled={currentPath === "."}>
        ↑ ..
      </button>
      <code className="files-current-path">{currentPath}</code>
      <button type="button" className="btn btn--sm" onClick={onRefresh}>
        🔄 刷新
      </button>
    </div>
  );
}
