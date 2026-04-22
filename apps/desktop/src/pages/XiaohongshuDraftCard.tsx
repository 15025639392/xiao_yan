import { useEffect, useState } from "react";

import type {
  XiaohongshuCoverPreviewResponse,
  XiaohongshuCreatorPreviewItem,
  XiaohongshuLeadCaptureResponse,
  XiaohongshuPublishAutofillResponse,
  XiaohongshuPublishViaMcpResponse,
  XiaohongshuTextImageAutofillResponse,
} from "../lib/api";
import { previewXiaohongshuCover } from "../lib/api";
import { Button } from "../components/ui";
import type {
  XiaohongshuImageCardDraft,
  XiaohongshuLeadCaptureTemplate,
  XiaohongshuLeadFollowUpPacket,
  XiaohongshuPublishChecklist,
  XiaohongshuPublishDraft,
} from "./xiaohongshuPageHelpers";
import type { XiaohongshuLeadReplyPlan } from "./xiaohongshuLeadReplyHelpers";
import { XiaohongshuLeadQueue } from "./XiaohongshuLeadQueue";

type XiaohongshuDraftCardProps = {
  item: XiaohongshuCreatorPreviewItem;
  index: number;
  draft?: XiaohongshuPublishDraft;
  imageDraft?: XiaohongshuImageCardDraft;
  publishChecklist?: XiaohongshuPublishChecklist;
  followUpPacket?: XiaohongshuLeadFollowUpPacket;
  leadCaptureTemplate?: XiaohongshuLeadCaptureTemplate;
  leadCaptureResult?: XiaohongshuLeadCaptureResponse;
  leadReplyPlan?: XiaohongshuLeadReplyPlan;
  autofillResult?: XiaohongshuPublishAutofillResponse;
  publishViaMcpResult?: XiaohongshuPublishViaMcpResponse;
  textImageResult?: XiaohongshuTextImageAutofillResponse;
  autofilling: boolean;
  autoPublishing: boolean;
  publishViaMcpPending: boolean;
  textImageFilling: boolean;
  leadCapturing: boolean;
  imagePathsText: string;
  onExpand: () => void;
  onAutofill: () => void;
  onAutoPublish: () => void;
  onImagePathsChange: (value: string) => void;
  onPublishViaMcp: () => void;
  onTextImageAutofill: () => void;
  onLeadCapture: () => void;
};

const TEMPLATE_LABELS: Record<string, string> = {
  warm_story: "故事感",
  expert_clean: "专业感",
  bold_hook: "强钩子",
};

export function XiaohongshuDraftCard({
  item,
  index,
  draft,
  imageDraft,
  publishChecklist,
  followUpPacket,
  leadCaptureTemplate,
  leadCaptureResult,
  leadReplyPlan,
  autofillResult,
  publishViaMcpResult,
  textImageResult,
  autofilling,
  autoPublishing,
  publishViaMcpPending,
  textImageFilling,
  leadCapturing,
  imagePathsText,
  onExpand,
  onAutofill,
  onAutoPublish,
  onImagePathsChange,
  onPublishViaMcp,
  onTextImageAutofill,
  onLeadCapture,
}: XiaohongshuDraftCardProps) {
  const [coverPreview, setCoverPreview] = useState<XiaohongshuCoverPreviewResponse | null>(null);
  const [coverPreviewLoading, setCoverPreviewLoading] = useState(false);
  const [coverPreviewError, setCoverPreviewError] = useState("");
  const action = item.platform_result.actions[0];
  const lead = item.lead_assessment;
  const textImageButtonLabel =
    textImageResult?.status === "needs_manual_expand"
      ? "我已点再写一张，继续填正文页"
      : textImageFilling
        ? "生成图卡中..."
        : "生成3张图卡并尝试填入";

  useEffect(() => {
    let cancelled = false;
    async function loadInitialPreview() {
      if (!draft) {
        setCoverPreview(null);
        setCoverPreviewError("");
        return;
      }
      setCoverPreviewLoading(true);
      setCoverPreviewError("");
      try {
        const result = await previewXiaohongshuCover({
          title: draft.title,
          body: draft.body,
        });
        if (!cancelled) {
          setCoverPreview(result);
        }
      } catch (error) {
        if (!cancelled) {
          setCoverPreview(null);
          setCoverPreviewError(error instanceof Error ? error.message : "生成封面预览失败");
        }
      } finally {
        if (!cancelled) {
          setCoverPreviewLoading(false);
        }
      }
    }
    void loadInitialPreview();
    return () => {
      cancelled = true;
    };
  }, [draft?.title, draft?.body]);

  async function handleSwitchCoverTemplate(templateName: string) {
    if (!draft) return;
    setCoverPreviewLoading(true);
    setCoverPreviewError("");
    try {
      const result = await previewXiaohongshuCover({
        title: draft.title,
        body: draft.body,
        template_name: templateName,
      });
      setCoverPreview(result);
    } catch (error) {
      setCoverPreviewError(error instanceof Error ? error.message : "切换封面模板失败");
    } finally {
      setCoverPreviewLoading(false);
    }
  }

  return (
    <article key={`${item.platform_result.event.text.slice(0, 20)}-${index}`} className="xhs-result-card">
      <div className="xhs-result-card__meta">
        <span className="xhs-result-card__tag">{item.platform_result.event.event_type}</span>
        {lead ? <span className="xhs-result-card__tag">{lead.suggested_action}</span> : null}
      </div>
      <h3 className="xhs-result-card__title">{action?.title || `候选 ${index + 1}`}</h3>
      <p className="xhs-result-card__source">{item.platform_result.event.text}</p>
      <div className="xhs-result-card__content">
        <strong>草稿内容</strong>
        <p>{action?.content || item.output_text}</p>
      </div>
      <div className="xhs-result-card__actions">
        <Button type="button" variant="secondary" onClick={onExpand}>
          展开成完整图文稿
        </Button>
        <Button type="button" onClick={onAutofill} disabled={autofilling}>
          {autofilling ? "填充中..." : "打开发布页并尝试填充"}
        </Button>
        <Button type="button" variant="primary" onClick={onAutoPublish} disabled={autoPublishing}>
          {autoPublishing ? "自动发布中..." : "全自动发布"}
        </Button>
        <Button type="button" variant="secondary" onClick={onPublishViaMcp} disabled={publishViaMcpPending}>
          {publishViaMcpPending ? "MCP 发布中..." : "用 MCP 发布图文"}
        </Button>
        <Button type="button" variant="secondary" onClick={onTextImageAutofill} disabled={textImageFilling}>
          {textImageButtonLabel}
        </Button>
      </div>
      {draft ? (
        <div className="xhs-result-card__expanded">
          <strong>可发图文稿</strong>
          <div className="xhs-result-card__actions">
            <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(draft.title)}>
              复制标题
            </Button>
            <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(draft.body)}>
              复制正文
            </Button>
          </div>
          <pre>{draft.fullText}</pre>
          <div className="xhs-result-card__expanded">
            <strong>封面模板预览</strong>
            <div className="xhs-result-card__actions">
              {(coverPreview?.available_templates || Object.keys(TEMPLATE_LABELS)).map((templateName) => (
                <Button
                  key={templateName}
                  type="button"
                  variant={coverPreview?.template_name === templateName ? "default" : "secondary"}
                  disabled={coverPreviewLoading}
                  onClick={() => {
                    void handleSwitchCoverTemplate(templateName);
                  }}
                >
                  {TEMPLATE_LABELS[templateName] || templateName}
                </Button>
              ))}
            </div>
            {coverPreviewLoading ? <p className="xhs-result-card__hint">封面预览生成中...</p> : null}
            {coverPreviewError ? <p className="xhs-result-card__hint">封面预览：{coverPreviewError}</p> : null}
            {coverPreview ? (
              <div className="xhs-cover-preview">
                <img
                  className="xhs-cover-preview__image"
                  src={coverPreview.image_data_url}
                  alt={`封面预览-${coverPreview.template_name}`}
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      {imageDraft ? (
        <div className="xhs-result-card__expanded">
          <strong>3 张图卡文案</strong>
          <div className="xhs-result-card__actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(imageDraft.cards.join("\n\n---\n\n"))}
            >
              复制图卡文案
            </Button>
            {textImageResult?.status === "needs_manual_expand" ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  const nextIndex = Math.min(textImageResult.filled_cards, imageDraft.cards.length - 1);
                  void navigator.clipboard.writeText(imageDraft.cards[nextIndex] || imageDraft.cards[imageDraft.cards.length - 1]);
                }}
              >
                复制下一张图卡
              </Button>
            ) : null}
          </div>
          <pre>{imageDraft.fullText}</pre>
        </div>
      ) : null}
      {publishChecklist ? (
        <div className="xhs-result-card__expanded">
          <strong>发布包</strong>
          <div className="xhs-result-card__actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(publishChecklist.firstComment)}
            >
              复制首评
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(publishChecklist.publishPacketText)}
            >
              复制发布清单
            </Button>
          </div>
          <pre>{publishChecklist.publishPacketText}</pre>
        </div>
      ) : null}
      <div className="xhs-result-card__expanded">
        <strong>MCP 发布图片路径</strong>
        <p>先填本地绝对路径，每行一张图。第一版只支持本地文件。</p>
        <textarea
          value={imagePathsText}
          onChange={(event) => onImagePathsChange(event.target.value)}
          placeholder={"/Users/you/Desktop/xhs-cover.png\n/Users/you/Desktop/xhs-page-2.png"}
          rows={3}
        />
      </div>
      {followUpPacket ? (
        <div className="xhs-result-card__expanded">
          <strong>承接包</strong>
          <div className="xhs-result-card__actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(followUpPacket.commentReply)}
            >
              复制评论回复
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(followUpPacket.directMessage)}
            >
              复制私信承接
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigator.clipboard.writeText(followUpPacket.wechatBridge)}
            >
              复制微信导流
            </Button>
          </div>
          <pre>{followUpPacket.followUpPacketText}</pre>
        </div>
      ) : null}
      {leadCaptureTemplate ? (
        <div className="xhs-result-card__expanded">
          <strong>线索记录模板</strong>
          <div className="xhs-result-card__actions">
            <Button type="button" onClick={onLeadCapture} disabled={leadCapturing}>
              {leadCapturing ? "提取中..." : "从当前页自动提取"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                void navigator.clipboard.writeText(leadCaptureResult?.tracking_template || leadCaptureTemplate.trackingTemplate)
              }
            >
              复制线索模板
            </Button>
          </div>
          <pre>{leadCaptureResult?.tracking_template || leadCaptureTemplate.trackingTemplate}</pre>
        </div>
      ) : null}
      {leadReplyPlan ? (
        <XiaohongshuLeadQueue plan={leadReplyPlan} />
      ) : null}
      {autofillResult ? <p className="xhs-result-card__hint">发布页状态：{autofillResult.message}</p> : null}
      {publishViaMcpResult ? (
        <p className="xhs-result-card__hint">
          {publishViaMcpResult.message}
          {publishViaMcpResult.post_url ? ` ${publishViaMcpResult.post_url}` : ""}
        </p>
      ) : null}
      {textImageResult ? <p className="xhs-result-card__hint">图卡状态：{textImageResult.message}</p> : null}
      {leadCaptureResult ? <p className="xhs-result-card__hint">线索提取：{leadCaptureResult.message}</p> : null}
      {lead?.follow_up_hint ? <p className="xhs-result-card__hint">经营建议：{lead.follow_up_hint}</p> : null}
    </article>
  );
}
