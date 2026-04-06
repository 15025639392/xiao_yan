type MemoryDeleteModalProps = {
  open: boolean;
  contentPreview: string;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function MemoryDeleteModal({ open, contentPreview, deleting, onCancel, onConfirm }: MemoryDeleteModalProps) {
  if (!open) return null;

  return (
    <div className="memory-delete-modal-overlay" onClick={onCancel}>
      <div className="memory-delete-modal" onClick={(e) => e.stopPropagation()}>
        <div className="memory-delete-modal__header">
          <span className="memory-delete-modal__icon">🗑️</span>
          <h4>确认删除记忆？</h4>
        </div>
        <div className="memory-delete-modal__content">
          <p className="memory-delete-modal__warning">此操作不可恢复。</p>
          <div className="memory-delete-modal__preview">
            <span className="memory-delete-modal__preview-label">记忆内容：</span>
            <p className="memory-delete-modal__preview-text">{contentPreview}</p>
          </div>
        </div>
        <div className="memory-delete-modal__actions">
          <button className="memory-delete-modal__btn memory-delete-modal__btn--cancel" onClick={onCancel} disabled={deleting}>
            取消
          </button>
          <button className="memory-delete-modal__btn memory-delete-modal__btn--confirm" onClick={onConfirm} disabled={deleting}>
            {deleting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}

