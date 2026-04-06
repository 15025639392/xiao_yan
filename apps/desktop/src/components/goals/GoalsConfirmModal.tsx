type GoalsConfirmModalProps = {
  isOpen: boolean;
  goalTitle: string;
  action: "abandon" | "complete";
  onConfirm: () => void;
  onCancel: () => void;
};

export function GoalsConfirmModal({
  isOpen,
  goalTitle,
  action,
  onConfirm,
  onCancel,
}: GoalsConfirmModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">{action === "abandon" ? "确认放弃目标" : "确认完成目标"}</h3>
        </div>
        <div className="modal__body">
          <p>
            {action === "abandon"
              ? `确定要放弃目标 "${goalTitle}" 吗？此操作不可撤销。`
              : `确定要完成目标 "${goalTitle}" 吗？`}
          </p>
        </div>
        <div className="modal__footer">
          <button className="btn btn--secondary" onClick={onCancel} type="button">
            取消
          </button>
          <button
            className={`btn ${action === "abandon" ? "btn--danger" : "btn--primary"}`}
            onClick={onConfirm}
            type="button"
          >
            {action === "abandon" ? "确认放弃" : "确认完成"}
          </button>
        </div>
      </div>
    </div>
  );
}

