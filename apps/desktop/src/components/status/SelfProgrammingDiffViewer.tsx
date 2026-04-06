import { useState } from "react";
import type { SelfProgrammingEdit } from "../../lib/api";

type SelfProgrammingDiffViewerProps = {
  edit: SelfProgrammingEdit;
};

export function SelfProgrammingDiffViewer({ edit }: SelfProgrammingDiffViewerProps) {
  const [expanded, setExpanded] = useState(false);

  if (edit.kind === "create") {
    return (
      <div className="si-diff-block">
        <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
          <span className="si-diff-kind si-diff-kind--create">CREATE</span>
          <code className="si-diff-path">{edit.file_path}</code>
          <svg
            className="si-diff-arrow"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{ transform: expanded ? "rotate(180deg)" : "none" }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
        {expanded ? (
          <pre className="si-diff-content si-diff-content--new">
            <code>
              {(edit.file_content ?? "").slice(0, 2000)}
              {(edit.file_content?.length ?? 0) > 2000 ? "\n... (截断)" : ""}
            </code>
          </pre>
        ) : null}
      </div>
    );
  }

  if (edit.kind === "insert") {
    return (
      <div className="si-diff-block">
        <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
          <span className="si-diff-kind si-diff-kind--insert">INSERT</span>
          <code className="si-diff-path">{edit.file_path}</code>
        </div>
        {expanded ? (
          <div className="si-diff-content-wrapper">
            <pre className="si-diff-content si-diff-content--context">
              <code>... {edit.insert_after ?? "..."} ...</code>
            </pre>
            <pre className="si-diff-content si-diff-content--new">
              <code>+ {(edit.replace_text ?? "").slice(0, 1000)}</code>
            </pre>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="si-diff-block">
      <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
        <span className="si-diff-kind si-diff-kind--replace">REPLACE</span>
        <code className="si-diff-path">{edit.file_path}</code>
        <svg
          className="si-diff-arrow"
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{ transform: expanded ? "rotate(180deg)" : "none" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {expanded ? (
        <div className="si-diff-content-wrapper">
          <pre className="si-diff-content si-diff-content--removed">
            <code>- {(edit.search_text ?? "").slice(0, 1000)}</code>
          </pre>
          <pre className="si-diff-content si-diff-content--new">
            <code>+ {(edit.replace_text ?? "").slice(0, 1000)}</code>
          </pre>
        </div>
      ) : null}
    </div>
  );
}

