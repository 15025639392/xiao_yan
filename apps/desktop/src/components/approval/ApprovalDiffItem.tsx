import { useState } from "react";
import type { SelfProgrammingEdit } from "../../lib/api";

type ApprovalDiffItemProps = {
  edit: SelfProgrammingEdit;
};

export function ApprovalDiffItem({ edit }: ApprovalDiffItemProps) {
  const [expanded, setExpanded] = useState(false);

  const kindLabel = edit.kind.toUpperCase();
  const kindClass =
    edit.kind === "create"
      ? "approval-diff-kind--create"
      : edit.kind === "insert"
        ? "approval-diff-kind--insert"
        : "approval-diff-kind--replace";

  return (
    <div className="approval-diff-item">
      <div className="approval-diff-header" onClick={() => setExpanded(!expanded)}>
        <span className={`approval-diff-kind ${kindClass}`}>{kindLabel}</span>
        <code className="approval-diff-path">{edit.file_path}</code>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform 200ms" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {expanded ? (
        <div className="approval-diff-content">
          {edit.kind === "create" ? (
            <pre>
              <code>{(edit.file_content ?? "").slice(0, 1500)}</code>
            </pre>
          ) : edit.kind === "insert" ? (
            <div>
              <pre className="approval-diff-ctx">
                <code>... {edit.insert_after ?? "..."} ...</code>
              </pre>
              <pre className="approval-diff-new">
                <code>+ {(edit.replace_text ?? "").slice(0, 800)}</code>
              </pre>
            </div>
          ) : (
            <div>
              <pre className="approval-diff-old">
                <code>- {(edit.search_text ?? "").slice(0, 800)}</code>
              </pre>
              <pre className="approval-diff-new">
                <code>+ {(edit.replace_text ?? "").slice(0, 800)}</code>
              </pre>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
