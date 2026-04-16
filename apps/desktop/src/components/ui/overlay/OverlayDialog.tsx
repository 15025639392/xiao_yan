import type { ReactNode } from "react";
import { Dialog, DialogContent } from "../dialog";

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
  return (
    <Dialog open={isOpen} onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent className={contentClassName} overlayClassName={overlayClassName} aria-describedby={undefined}>
        {children}
      </DialogContent>
    </Dialog>
  );
}
