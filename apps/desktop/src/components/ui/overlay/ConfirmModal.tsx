import type { ReactNode } from "react";
import type { ModalActionItem } from "../actions/ModalActionButtons";
import { ActionModal } from "./ActionModal";

type ConfirmTone = "primary" | "danger";
type ConfirmButtonSize = "default" | "sm";
type ConfirmActionItem = ModalActionItem;

type ConfirmModalProps = {
  isOpen?: boolean;
  title: ReactNode;
  onCancel: () => void;
  onConfirm?: () => void;
  actions?: ConfirmActionItem[];
  footer?: ReactNode;
  variant?: "default" | "danger";
  confirmTone?: ConfirmTone;
  confirmText?: ReactNode;
  cancelText?: ReactNode;
  confirmDisabled?: boolean;
  cancelDisabled?: boolean;
  confirmAutoFocus?: boolean;
  buttonSize?: ConfirmButtonSize;
  children: ReactNode;
};

export function ConfirmModal({
  isOpen = true,
  title,
  onCancel,
  onConfirm,
  actions,
  footer,
  variant = "default",
  confirmTone = "primary",
  confirmText = "确认",
  cancelText = "取消",
  confirmDisabled = false,
  cancelDisabled = false,
  confirmAutoFocus = false,
  buttonSize = "default",
  children,
}: ConfirmModalProps) {
  const fallbackActions: ModalActionItem[] = [
    { key: "cancel", label: cancelText, tone: "secondary", onClick: onCancel, disabled: cancelDisabled },
    {
      key: "confirm",
      label: confirmText,
      tone: confirmTone,
      onClick: onConfirm,
      disabled: confirmDisabled || !onConfirm,
      autoFocus: confirmAutoFocus,
    },
  ];
  const actionsContent = actions && actions.length > 0 ? actions : fallbackActions;

  return (
    <ActionModal
      isOpen={isOpen}
      title={title}
      onClose={onCancel}
      variant={variant}
      actions={actionsContent}
      actionsSize={buttonSize}
      footer={footer}
    >
      {children}
    </ActionModal>
  );
}
