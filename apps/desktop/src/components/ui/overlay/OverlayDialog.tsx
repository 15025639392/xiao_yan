import type { ReactNode } from "react";

type OverlayDialogProps = {
  isOpen?: boolean;
  onClose: () => void;
  overlayClassName?: string;
  contentClassName?: string;
  children: ReactNode;
};

export function OverlayDialog({
  isOpen = true,
  onClose,
  overlayClassName = "modal-overlay",
  contentClassName = "modal",
  children,
}: OverlayDialogProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className={overlayClassName} onClick={onClose}>
      <div className={contentClassName} onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        {children}
      </div>
    </div>
  );
}
