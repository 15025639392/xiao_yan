import type { ReactNode } from "react";
import { getModalActionButtonClass } from "../actions/ModalActionButtons";

type ConfigActionButtonTone = "default" | "primary";

type ConfigActionButtonProps = {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: ConfigActionButtonTone;
  classNamePrefix?: string;
  type?: "button" | "submit" | "reset";
};

export function ConfigActionButton({
  children,
  onClick,
  disabled = false,
  tone = "default",
  classNamePrefix = "config-panel",
  type = "button",
}: ConfigActionButtonProps) {
  const classes = getModalActionButtonClass({
    style: "config",
    tone,
    classNamePrefix,
  });

  return (
    <button type={type} className={classes} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
