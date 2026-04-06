import type { SelfProgrammingJobState } from "./selfProgrammingTypes";
import { SelfProgrammingDiffViewer } from "./SelfProgrammingDiffViewer";

type SelfProgrammingEditsSectionProps = {
  edits: NonNullable<SelfProgrammingJobState["edits"]>;
  showDiff: boolean;
  onToggle: () => void;
};

export function SelfProgrammingEditsSection({ edits, showDiff, onToggle }: SelfProgrammingEditsSectionProps) {
  if (edits.length === 0) {
    return null;
  }

  return (
    <div className="si-section">
      <button type="button" className="si-diff-toggle" onClick={onToggle}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          {showDiff ? <polyline points="18 15 12 9 6 15" /> : <polyline points="6 9 12 15 18 9" />}
        </svg>
        <span>代码变更 ({edits.length} 个编辑)</span>
        <span className="si-diff-count">{edits.length}</span>
      </button>
      {showDiff ? (
        <div className="si-diff-list">
          {edits.map((edit, index) => (
            <SelfProgrammingDiffViewer key={`${edit.file_path}-${index}`} edit={edit} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
