import type { FileReadResult } from "../../lib/api";
import { formatBytes } from "../../lib/utils";

type FileViewerProps = {
  fileContent: FileReadResult;
  onClose: () => void;
};

export function FileViewer({ fileContent, onClose }: FileViewerProps) {
  return (
    <div className="file-viewer">
      <div className="file-viewer__header">
        <code>{fileContent.path}</code>
        <button type="button" className="btn btn--sm" onClick={onClose}>
          ✕ 关闭
        </button>
      </div>
      <div className="file-viewer__meta">
        {fileContent.line_count} 行 · {formatBytes(fileContent.size_bytes)}
        {fileContent.truncated ? " · 已截断" : ""}
        {fileContent.mime_type ? ` · ${fileContent.mime_type}` : ""}
      </div>
      <pre className="file-viewer__content">{fileContent.content}</pre>
    </div>
  );
}
