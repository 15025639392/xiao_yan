import type { ReactNode } from "react";

export type ModalActionTone = "default" | "secondary" | "primary" | "danger";
export type ModalActionStyle = "system" | "config";
export type ModalActionSize = "default" | "sm";

export type ModalActionItem = {
  key: string;
  label: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: ModalActionTone;
  autoFocus?: boolean;
  type?: "button" | "submit" | "reset";
};

type ModalActionButtonsProps = {
  actions: ModalActionItem[];
  style?: ModalActionStyle;
  size?: ModalActionSize;
  classNamePrefix?: string;
};

function resolveSystemToneClass(tone: ModalActionTone): string {
  if (tone === "danger") return "btn--danger";
  if (tone === "primary") return "btn--primary";
  return "btn--secondary";
}

export function getModalActionButtonClass({
  style,
  tone = "default",
  size = "default",
  classNamePrefix = "config-panel",
}: {
  style: ModalActionStyle;
  tone?: ModalActionTone;
  size?: ModalActionSize;
  classNamePrefix?: string;
}): string {
  if (style === "config") {
    const classes = [`${classNamePrefix}__btn`];
    if (tone === "primary") {
      classes.push(`${classNamePrefix}__btn--primary`);
    }
    return classes.join(" ");
  }

  const classes = ["btn", resolveSystemToneClass(tone)];
  if (size === "sm") {
    classes.push("btn--sm");
  }
  return classes.join(" ");
}

export function ModalActionButtons({
  actions,
  style = "system",
  size = "default",
  classNamePrefix = "config-panel",
}: ModalActionButtonsProps) {
  return (
    <>
      {actions.map((action) => (
        <button
          key={action.key}
          type={action.type ?? "button"}
          className={getModalActionButtonClass({
            style,
            tone: action.tone,
            size,
            classNamePrefix,
          })}
          onClick={action.onClick}
          disabled={action.disabled}
          autoFocus={action.autoFocus}
        >
          {action.label}
        </button>
      ))}
    </>
  );
}
