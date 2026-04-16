import { Button, Input, Textarea } from "../ui";

type PersonaBasicTabProps = {
  name: string;
  identity: string;
  originStory: string;
  saving: boolean;
  onNameChange: (value: string) => void;
  onIdentityChange: (value: string) => void;
  onOriginStoryChange: (value: string) => void;
  onSave: () => void;
  onReset: () => void;
  onInitialize: () => void;
};

export function PersonaBasicTab({
  name,
  identity,
  originStory,
  saving,
  onNameChange,
  onIdentityChange,
  onOriginStoryChange,
  onSave,
  onReset,
  onInitialize,
}: PersonaBasicTabProps) {
  return (
    <div className="persona-form">
      <div className="persona-form__section">
        <h4 className="persona-form__section-title">身份信息</h4>

        <div className="persona-form__field">
          <label className="persona-form__label" htmlFor="wb-persona-name">
            名字
            <span className="persona-form__hint">数字人的称呼</span>
          </label>
          <Input
            id="wb-persona-name"
            type="text"
            className="persona-form__input"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            maxLength={20}
            placeholder="例如：小晏"
          />
        </div>

        <div className="persona-form__field">
          <label className="persona-form__label" htmlFor="wb-persona-identity">
            身份
            <span className="persona-form__hint">自我认知的身份描述</span>
          </label>
          <Input
            id="wb-persona-identity"
            type="text"
            className="persona-form__input"
            value={identity}
            onChange={(e) => onIdentityChange(e.target.value)}
            maxLength={50}
            placeholder="例如：AI 助手"
          />
        </div>

        <div className="persona-form__field">
          <label className="persona-form__label" htmlFor="wb-persona-origin">
            背景故事
            <span className="persona-form__hint">起源和成长经历（影响叙事风格）</span>
          </label>
          <Textarea
            id="wb-persona-origin"
            className="persona-form__textarea"
            value={originStory}
            onChange={(e) => onOriginStoryChange(e.target.value)}
            rows={4}
            maxLength={300}
            placeholder="描述这个数字人的来历..."
          />
        </div>
      </div>

      <div className="persona-form__actions">
        <Button type="button" variant="default" onClick={onSave} disabled={saving}>
          {saving ? "保存中..." : "保存更改"}
        </Button>
        <Button type="button" variant="ghost" onClick={onReset} disabled={saving}>
          重置默认
        </Button>
        <Button type="button" variant="destructive" onClick={onInitialize} disabled={saving}>
          🔄 初始化数字人
        </Button>
      </div>
    </div>
  );
}
