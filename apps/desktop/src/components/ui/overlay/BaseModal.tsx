import type { ReactNode } from "react";

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
  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className={`modal${variant === "danger" ? " modal--danger" : ""}`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal__header">
          <h3 className="modal__title">{title}</h3>
        </div>
        <div className="modal__body">{children}</div>
        {footer ? <div className="modal__footer">{footer}</div> : null}
      </div>
    </div>
  );
}
