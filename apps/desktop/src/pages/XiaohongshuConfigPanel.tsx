import { Button } from "../components/ui";

type XiaohongshuConfigPanelProps = {
  accountName: string;
  onAccountNameChange: (value: string) => void;
  scoutingInterval: number;
  onScoutingIntervalChange: (value: number) => void;
  publishMode: "manual" | "auto";
  onPublishModeChange: (value: "manual" | "auto") => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
};

export function XiaohongshuConfigPanel({
  accountName,
  onAccountNameChange,
  scoutingInterval,
  onScoutingIntervalChange,
  publishMode,
  onPublishModeChange,
  onSave,
  onCancel,
  saving,
}: XiaohongshuConfigPanelProps) {
  return (
    <section className="xhs-config-panel">
      <h3 className="xhs-config-panel__title">闭环配置</h3>
      <div className="xhs-config-panel__fields">
        <label className="xhs-config-field">
          <span className="xhs-config-field__label">小红书账号名</span>
          <input
            type="text"
            className="xhs-config-field__input"
            value={accountName}
            placeholder="例如：小红薯66661C17"
            onChange={(e) => onAccountNameChange(e.target.value)}
          />
        </label>
        <label className="xhs-config-field">
          <span className="xhs-config-field__label">侦察间隔（小时）</span>
          <input
            type="number"
            className="xhs-config-field__input"
            value={scoutingInterval}
            min={0.1}
            max={24}
            step={0.1}
            onChange={(e) => onScoutingIntervalChange(parseFloat(e.target.value) || 1.0)}
          />
        </label>
        <label className="xhs-config-field">
          <span className="xhs-config-field__label">发布模式</span>
          <select
            className="xhs-config-field__input"
            value={publishMode}
            onChange={(e) => onPublishModeChange(e.target.value === "auto" ? "auto" : "manual")}
          >
            <option value="manual">手动发布</option>
            <option value="auto">自动发布</option>
          </select>
        </label>
      </div>
      <div className="xhs-config-panel__actions">
        <Button type="default" onClick={onCancel}>取消</Button>
        <Button type="primary" onClick={onSave} disabled={saving}>
          {saving ? "保存中..." : "保存"}
        </Button>
      </div>
    </section>
  );
}
