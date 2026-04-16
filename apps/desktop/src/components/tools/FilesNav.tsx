import { Button } from "../ui";

type FilesNavProps = {
  currentPath: string;
  onNavigateUp: () => void;
  onRefresh: () => void;
};

export function FilesNav({ currentPath, onNavigateUp, onRefresh }: FilesNavProps) {
  return (
    <div className="files-nav">
      <Button type="button" variant="secondary" size="sm" onClick={onNavigateUp} disabled={currentPath === "."}>
        ↑ ..
      </Button>
      <code className="files-current-path">{currentPath}</code>
      <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
        🔄 刷新
      </Button>
    </div>
  );
}
