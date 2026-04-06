import { ConfirmModal } from "../ui";

type MemoryDeleteModalProps = {
  open: boolean;
  contentPreview: string;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function MemoryDeleteModal({ open, contentPreview, deleting, onCancel, onConfirm }: MemoryDeleteModalProps) {
  return (
    <ConfirmModal
      isOpen={open}
      title="🗑️ 确认删除记忆？"
      onCancel={onCancel}
      variant="danger"
      actions={[
        { key: "cancel", label: "取消", tone: "secondary", onClick: onCancel, disabled: deleting },
        {
          key: "confirm",
          label: deleting ? "删除中..." : "确认删除",
          tone: "danger",
          onClick: onConfirm,
          disabled: deleting,
        },
      ]}
    >
      <p className="memory-delete-modal__warning">此操作不可恢复。</p>
      <div className="memory-delete-modal__preview">
        <span className="memory-delete-modal__preview-label">记忆内容：</span>
        <p className="memory-delete-modal__preview-text">{contentPreview}</p>
      </div>
    </ConfirmModal>
  );
}
