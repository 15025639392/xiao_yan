import { ConfirmModal } from "../ui";

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
    <ConfirmModal
      title="⚠️ 确认回滚"
      onCancel={onCancel}
      variant="danger"
      buttonSize="sm"
      actions={[
        { key: "cancel", label: "取消", tone: "secondary", onClick: onCancel, disabled: rollingBack },
        {
          key: "confirm",
          label: rollingBack ? "⏳ 执行中..." : "确认回滚",
          tone: "danger",
          onClick: onConfirm,
          autoFocus: true,
        },
      ]}
    >
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
    </ConfirmModal>
  );
}
