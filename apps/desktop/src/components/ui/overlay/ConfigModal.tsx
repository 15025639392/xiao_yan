import type { ReactNode } from "react";
import type { ConfigActionItem } from "../config/ConfigActions";
import { ActionModal } from "./ActionModal";

type ConfigModalProps = {
  isOpen?: boolean;
  title: ReactNode;
  onClose: () => void;
  actions?: ConfigActionItem[];
  footer?: ReactNode;
  error?: ReactNode;
  classNamePrefix?: string;
  children: ReactNode;
};

export function ConfigModal({
  isOpen = true,
  title,
  onClose,
  actions,
  footer,
  error,
  classNamePrefix = "config-panel",
  children,
}: ConfigModalProps) {
  const rootClass = classNamePrefix;

  return (
    <ActionModal
      isOpen={isOpen}
      title={title}
      onClose={onClose}
      overlayClassName={`${rootClass}-overlay`}
      contentClassName={rootClass}
      headerClassName={`${rootClass}__header`}
      titleClassName={`${rootClass}__title`}
      bodyClassName={`${rootClass}__body`}
      footerClassName={`${rootClass}__footer`}
      errorClassName={`${rootClass}__error`}
      closeButton={{
        show: true,
        className: `${rootClass}__close`,
        ariaLabel: "关闭",
        content: "×",
      }}
      actions={actions}
      actionsStyle="config"
      actionsClassNamePrefix={classNamePrefix}
      footer={footer}
      error={error}
    >
      {children}
    </ActionModal>
  );
}
