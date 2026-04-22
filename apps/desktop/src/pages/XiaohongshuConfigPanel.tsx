import { Button } from "../components/ui";

type XiaohongshuConfigPanelProps = {
  accountName: string;
  onAccountNameChange: (value: string) => void;
  scoutingInterval: number;
  onScoutingIntervalChange: (value: number) => void;
  publishMode: "review_before_publish" | "direct_publish";
  onPublishModeChange: (value: "review_before_publish" | "direct_publish") => void;
  autoPublishSelector: string;
  onAutoPublishSelectorChange: (value: string) => void;
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
  autoPublishSelector,
  onAutoPublishSelectorChange,
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
            onChange={(e) => onPublishModeChange(e.target.value as "review_before_publish" | "direct_publish")}
          >
            <option value="review_before_publish">准备到发布前，人工确认</option>
            <option value="direct_publish">自动直发</option>
          </select>
        </label>
        <label className="xhs-config-field">
          <span className="xhs-config-field__label">发布按钮 Selector</span>
          <input
            type="text"
            className="xhs-config-field__input"
            value={autoPublishSelector}
            placeholder={publishMode === "direct_publish" ? "自动发现（留空）" : "仅直发模式需要"}
            onChange={(e) => onAutoPublishSelectorChange(e.target.value)}
          />
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
