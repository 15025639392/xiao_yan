import { ModalActionButtons } from "../actions/ModalActionButtons";
import type { ModalActionItem } from "../actions/ModalActionButtons";

export type ConfigActionTone = "default" | "primary";
export type ConfigActionItem = Omit<ModalActionItem, "tone"> & { tone?: ConfigActionTone };

type ConfigActionsProps = {
  actions: ConfigActionItem[];
  classNamePrefix?: string;
};

export function ConfigActions({ actions, classNamePrefix = "config-panel" }: ConfigActionsProps) {
  const normalizedActions: ModalActionItem[] = actions.map((action) => ({
    ...action,
    tone: action.tone ?? "default",
  }));

  return (
    <ModalActionButtons
      actions={normalizedActions}
      style="config"
      classNamePrefix={classNamePrefix}
    />
  );
}
