import type { AppConfig } from "../../lib/api";
import { ConfigModal, RangeSettingField } from "../ui";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  onUpdate: (config: Partial<AppConfig>) => void;
  onClose: () => void;
};

const CONTEXT_LIMIT_PRESETS = [
  { label: "保守 (3)", value: 3 },
  { label: "默认 (6)", value: 6 },
  { label: "开放 (10)", value: 10 },
];

export function ChatConfigPanel({ config, isUpdating, error, onUpdate, onClose }: ChatConfigPanelProps) {
  return (
    <ConfigModal
      title="配置"
      onClose={onClose}
      error={error}
      actions={[{ key: "done", label: "完成", tone: "primary", onClick: onClose }]}
    >
      <RangeSettingField
        label="聊天上下文限制"
        description="每次聊天时携带的相关事件数量。值越小响应越快，但连贯性可能降低；值越大对话越连贯，但响应可能变慢。"
        min={1}
        max={20}
        value={config.chat_context_limit}
        presets={CONTEXT_LIMIT_PRESETS}
        disabled={isUpdating}
        onChange={(value) => onUpdate({ chat_context_limit: value })}
      />
    </ConfigModal>
  );
}
