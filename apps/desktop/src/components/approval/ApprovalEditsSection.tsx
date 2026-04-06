import type { SelfProgrammingEdit } from "../../lib/api";
import { ApprovalDiffItem } from "./ApprovalDiffItem";

type ApprovalEditsSectionProps = {
  edits: SelfProgrammingEdit[];
  showEdits: boolean;
  onToggle: () => void;
};

export function ApprovalEditsSection({ edits, showEdits, onToggle }: ApprovalEditsSectionProps) {
  if (edits.length === 0) {
    return null;
  }

  return (
    <div className="approval-edits">
      <button type="button" className="approval-edits__toggle" onClick={onToggle}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{ transform: showEdits ? "rotate(180deg)" : "none", transition: "transform 200ms ease" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
        <span>查看代码变更 ({edits.length})</span>
      </button>
      {showEdits ? (
        <div className="approval-edits__list">
          {edits.map((edit, index) => (
            <ApprovalDiffItem key={`${edit.file_path}-${index}`} edit={edit} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
