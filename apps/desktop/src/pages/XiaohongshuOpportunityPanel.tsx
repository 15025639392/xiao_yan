import { Button, Panel } from "../components/ui";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";

type XiaohongshuOpportunityPanelProps = {
  rawSnapshotText: string;
  accountName: string;
  topicsText: string;
  activitiesText: string;
  message: string;
  capturing: boolean;
  loading: boolean;
  onRawSnapshotChange: (value: string) => void;
  onAccountNameChange: (value: string) => void;
  onTopicsChange: (value: string) => void;
  onActivitiesChange: (value: string) => void;
  onMessageChange: (value: string) => void;
  onCapture: () => void;
  onExtract: () => void;
};

export function XiaohongshuOpportunityPanel({
  rawSnapshotText,
  accountName,
  topicsText,
  activitiesText,
  message,
  capturing,
  loading,
  onRawSnapshotChange,
  onAccountNameChange,
  onTopicsChange,
  onActivitiesChange,
  onMessageChange,
  onCapture,
  onExtract,
}: XiaohongshuOpportunityPanelProps) {
  return (
    <Panel
      icon="📥"
      title="创作首页机会"
      subtitle="直接粘贴创作服务平台首页里看到的话题和活动，一行一条。"
      className="xhs-page__panel"
    >
      <div className="xhs-form">
        <label className="xhs-form__field">
          <span className="xhs-form__label">创作首页原始文本</span>
          <Textarea
            value={rawSnapshotText}
            onChange={(event) => onRawSnapshotChange(event.target.value)}
            placeholder="把创作服务平台首页复制出来的文字粘进来"
            className="xhs-form__textarea"
          />
          <div className="xhs-form__actions">
            <Button type="button" onClick={onCapture} disabled={capturing || loading}>
              {capturing ? "读取中..." : "从当前创作首页自动读取"}
            </Button>
            <Button type="button" variant="secondary" onClick={onExtract}>
              自动提取话题和活动
            </Button>
            <span className="xhs-form__hint">适合直接粘贴页面里复制出来的原始文本，先粗提取再微调。</span>
          </div>
        </label>

        <label className="xhs-form__field">
          <span className="xhs-form__label">账号名</span>
          <Input value={accountName} onChange={(event) => onAccountNameChange(event.target.value)} />
        </label>

        <label className="xhs-form__field">
          <span className="xhs-form__label">创作话题</span>
          <Textarea
            value={topicsText}
            onChange={(event) => onTopicsChange(event.target.value)}
            placeholder="话题 | 参与人数 | 浏览量"
            className="xhs-form__textarea"
          />
          <span className="xhs-form__hint">格式：`话题 | 参与人数 | 浏览量`</span>
        </label>

        <label className="xhs-form__field">
          <span className="xhs-form__label">热门活动</span>
          <Textarea
            value={activitiesText}
            onChange={(event) => onActivitiesChange(event.target.value)}
            placeholder="活动标题 | 时间 | 激励提示"
            className="xhs-form__textarea"
          />
          <span className="xhs-form__hint">格式：`活动标题 | 时间 | 激励提示`</span>
        </label>

        <label className="xhs-form__field">
          <span className="xhs-form__label">草稿目标</span>
          <Textarea
            value={message}
            onChange={(event) => onMessageChange(event.target.value)}
            className="xhs-form__textarea xhs-form__textarea--short"
          />
        </label>
      </div>
    </Panel>
  );
}
