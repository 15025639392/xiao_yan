import { BaseModal } from "../ui";

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
  return (
    <BaseModal
      isOpen={isOpen}
      title={action === "abandon" ? "确认放弃目标" : "确认完成目标"}
      onClose={onCancel}
      footer={
        <>
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
        </>
      }
    >
      <p>
        {action === "abandon"
          ? `确定要放弃目标 "${goalTitle}" 吗？此操作不可撤销。`
          : `确定要完成目标 "${goalTitle}" 吗？`}
      </p>
    </BaseModal>
  );
}
