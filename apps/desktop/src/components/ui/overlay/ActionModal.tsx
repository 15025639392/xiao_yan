import type { ReactNode } from "react";
import { ModalActionButtons } from "../actions/ModalActionButtons";
import type { ModalActionItem } from "../actions/ModalActionButtons";
import type { ModalActionSize, ModalActionStyle } from "../actions/ModalActionButtons";
import { DialogTitle } from "../dialog";
import { OverlayDialog } from "./OverlayDialog";

type ActionModalCloseButton = {
  show?: boolean;
  className?: string;
  ariaLabel?: string;
  content?: ReactNode;
};

type ActionModalProps = {
  isOpen?: boolean;
  title: ReactNode;
  onClose: () => void;
  variant?: "default" | "danger";
  actions?: ModalActionItem[];
  actionsStyle?: ModalActionStyle;
  actionsSize?: ModalActionSize;
  actionsClassNamePrefix?: string;
  footer?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  overlayClassName?: string;
  contentClassName?: string;
  dangerContentClassName?: string;
  headerClassName?: string;
  titleClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  errorClassName?: string;
  closeButton?: ActionModalCloseButton;
};

export function ActionModal({
  isOpen = true,
  title,
  onClose,
  variant = "default",
  actions,
  actionsStyle = "system",
  actionsSize = "default",
  actionsClassNamePrefix = "config-panel",
  footer,
  error,
  children,
  overlayClassName = "modal-overlay",
  contentClassName = "modal",
  dangerContentClassName = "modal--danger",
  headerClassName = "modal__header",
  titleClassName = "modal__title",
  bodyClassName = "modal__body",
  footerClassName = "modal__footer",
  errorClassName = "modal__error",
  closeButton,
}: ActionModalProps) {
  const resolvedContentClassName =
    variant === "danger" && dangerContentClassName
      ? `${contentClassName} ${dangerContentClassName}`
      : contentClassName;

  const footerContent =
    footer ??
    (actions && actions.length > 0 ? (
      <ModalActionButtons
        actions={actions}
        style={actionsStyle}
        size={actionsSize}
        classNamePrefix={actionsClassNamePrefix}
      />
    ) : null);

  const showCloseButton = closeButton?.show ?? false;
  const closeButtonClassName = closeButton?.className ?? "modal__close";
  const closeButtonAriaLabel = closeButton?.ariaLabel ?? "关闭";
  const closeButtonContent = closeButton?.content ?? "×";

  return (
    <OverlayDialog
      isOpen={isOpen}
      onClose={onClose}
      overlayClassName={overlayClassName}
      contentClassName={resolvedContentClassName}
    >
      <div className={headerClassName}>
        <DialogTitle className={titleClassName}>{title}</DialogTitle>
        {showCloseButton ? (
          <button type="button" className={closeButtonClassName} onClick={onClose} aria-label={closeButtonAriaLabel}>
            {closeButtonContent}
          </button>
        ) : null}
      </div>

      <div className={bodyClassName}>{children}</div>

      {error ? <div className={errorClassName}>{error}</div> : null}

      {footerContent ? <div className={footerClassName}>{footerContent}</div> : null}
    </OverlayDialog>
  );
}
