import type { ReactNode } from "react";
import { ActionModal } from "./ActionModal";

type BaseModalProps = {
  isOpen?: boolean;
  title: ReactNode;
  onClose: () => void;
  variant?: "default" | "danger";
  footer?: ReactNode;
  children: ReactNode;
};

export function BaseModal({
  isOpen = true,
  title,
  onClose,
  variant = "default",
  footer,
  children,
}: BaseModalProps) {
  return (
    <ActionModal
      isOpen={isOpen}
      title={title}
      onClose={onClose}
      variant={variant}
      footer={footer}
    >
      {children}
    </ActionModal>
  );
}
