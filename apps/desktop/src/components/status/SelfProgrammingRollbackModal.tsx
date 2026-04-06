type SelfProgrammingRollbackModalProps = {
  touchedFiles: string[];
  rollingBack: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function SelfProgrammingRollbackModal({
  touchedFiles,
  rollingBack,
  onCancel,
  onConfirm,
}: SelfProgrammingRollbackModalProps) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal modal--danger" onClick={(event) => event.stopPropagation()} role="dialog">
        <div className="modal__header">
          <h3 className="modal__title">⚠️ 确认回滚</h3>
        </div>
        <div className="modal__body">
          <p style={{ margin: "0 0 var(--space-3)" }}>此操作将撤销自我编程对以下文件的修改，恢复到修改前的状态：</p>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "var(--text-secondary)" }}>
            {touchedFiles.map((filePath) => (
              <li key={filePath}>
                <code>{filePath}</code>
              </li>
            ))}
          </ul>
          <p style={{ margin: "var(--space-4) 0 0", color: "var(--danger)", fontWeight: 500 }}>
            ⚠️ 此操作不可自动重做。请确认要回滚吗？
          </p>
        </div>
        <div className="modal__footer">
          <button type="button" className="btn btn--sm" onClick={onCancel} disabled={rollingBack}>
            取消
          </button>
          <button type="button" className="btn btn--danger btn--sm" onClick={onConfirm} autoFocus>
            {rollingBack ? "⏳ 执行中..." : "确认回滚"}
          </button>
        </div>
      </div>
    </div>
  );
}
