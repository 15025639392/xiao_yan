import { ConfirmModal } from "../ui";

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
    <ConfirmModal
      isOpen={isOpen}
      title={action === "abandon" ? "确认放弃目标" : "确认完成目标"}
      onCancel={onCancel}
      actions={[
        { key: "cancel", label: "取消", tone: "secondary", onClick: onCancel },
        {
          key: "confirm",
          label: action === "abandon" ? "确认放弃" : "确认完成",
          tone: action === "abandon" ? "danger" : "primary",
          onClick: onConfirm,
        },
      ]}
    >
      <p>
        {action === "abandon"
          ? `确定要放弃目标 "${goalTitle}" 吗？此操作不可撤销。`
          : `确定要完成目标 "${goalTitle}" 吗？`}
      </p>
    </ConfirmModal>
  );
}
