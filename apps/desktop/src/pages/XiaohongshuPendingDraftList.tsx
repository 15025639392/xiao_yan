import type { XhsWorkDomainState } from "../lib/apiRuntime";
import type { XiaohongshuCoverPreviewResponse } from "../lib/apiXiaohongshu";
import { Button } from "../components/ui";
import { formatRelativeTimeZh } from "../lib/utils/time";

type DraftEdit = {
  title: string;
  body: string;
};

type XiaohongshuPendingDraftListProps = {
  drafts: XhsWorkDomainState["pending_drafts"];
  status: string;
  publishMode: "manual" | "auto";
  draftEdits: Record<string, DraftEdit>;
  draftCoverPreviews: Record<string, XiaohongshuCoverPreviewResponse | null>;
  draftCoverLoading: Record<string, boolean>;
  draftCoverErrors: Record<string, string>;
  onDraftEditChange: (draftId: string, patch: Partial<DraftEdit>) => void;
  onSwitchDraftCoverTemplate: (draftId: string, templateName: string) => void;
  onSaveDrafts: () => void;
  onPublishDraft: (draftId: string) => void;
  onDeleteDraft: (draftId: string) => void;
};

const COVER_TEMPLATE_LABELS: Record<string, string> = {
  warm_story: "故事感",
  expert_clean: "专业感",
  bold_hook: "强钩子",
};

function getTemplateLabel(templateName: string): string {
  return COVER_TEMPLATE_LABELS[templateName] || templateName;
}

export function XiaohongshuPendingDraftList({
  drafts,
  status,
  publishMode,
  draftEdits,
  draftCoverPreviews,
  draftCoverLoading,
  draftCoverErrors,
  onDraftEditChange,
  onSwitchDraftCoverTemplate,
  onSaveDrafts,
  onPublishDraft,
  onDeleteDraft,
}: XiaohongshuPendingDraftListProps) {
  if (drafts.length === 0) {
    return null;
  }

  return (
    <div className="xhs-page__pending-section">
      <h4 className="xhs-section-title">待发布草稿</h4>
      <ul className="xhs-pending-list">
        {drafts.map((draft) => {
          const coverPreview = draftCoverPreviews[draft.draft_id];
          const coverLoading = draftCoverLoading[draft.draft_id];
          const coverError = draftCoverErrors[draft.draft_id];
          const activeTemplate = coverPreview?.template_name;
          const availableTemplates = coverPreview?.available_templates;
          const isNext = drafts[0]?.draft_id === draft.draft_id;

          return (
          <li key={draft.draft_id} className="xhs-pending-item">
            {/* Status badges */}
            <div className="xhs-pending-item__status-row">
              <span className="xhs-pending-item__status">{draft.status}</span>
              {isNext ? (
                <span className="xhs-pending-item__status xhs-pending-item__status--next">下一条发布</span>
              ) : null}
              {draft.generated_at ? (
                <span className="xhs-pending-item__time">{formatRelativeTimeZh(draft.generated_at)}</span>
              ) : null}
            </div>

            {/* Cover image — hero element */}
            <div className="xhs-pending-item__cover">
              {coverLoading ? <div className="xhs-cover-loading" /> : null}
              {coverError ? <div className="xhs-cover-error">{coverError}</div> : null}
              {coverPreview ? (
                <>
                  <div className="xhs-cover-preview">
                    <img
                      className="xhs-cover-preview__image"
                      src={coverPreview.image_data_url}
                      alt={`待发布草稿封面-${coverPreview.template_name}`}
                    />
                  </div>
                  <p className="xhs-cover-preview__label">
                    {getTemplateLabel(coverPreview.template_name)} 模板
                  </p>
                </>
              ) : null}
            </div>

            {/* Template switcher pills */}
            {availableTemplates && availableTemplates.length > 0 ? (
              <div className="xhs-cover-template-pills">
                {availableTemplates.map((templateName) => (
                  <Button
                    key={templateName}
                    variant={activeTemplate === templateName ? "default" : "secondary"}
                    size="sm"
                    onClick={() => {
                      onSwitchDraftCoverTemplate(draft.draft_id, templateName);
                    }}
                    disabled={coverLoading}
                  >
                    {getTemplateLabel(templateName)}
                  </Button>
                ))}
              </div>
            ) : null}

            <hr className="xhs-pending-item__divider" />

            {/* Editable title + body */}
            <input
              className="xhs-pending-item__title-input"
              type="text"
              placeholder="标题"
              value={draftEdits[draft.draft_id]?.title ?? draft.title}
              onChange={(e) => onDraftEditChange(draft.draft_id, { title: e.target.value })}
            />
            <textarea
              className="xhs-pending-item__body-input"
              rows={4}
              placeholder="正文内容..."
              value={draftEdits[draft.draft_id]?.body ?? draft.body}
              onChange={(e) => onDraftEditChange(draft.draft_id, { body: e.target.value })}
            />

            {/* Action buttons */}
            <div className="xhs-pending-item__actions">
              <Button variant="outline" size="sm" onClick={onSaveDrafts}>
                保存修改
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => {
                  onPublishDraft(draft.draft_id);
                }}
                disabled={status === "reviewing"}
              >
                {publishMode === "auto" ? "优先自动发布" : "发布这条"}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (window.confirm("确定删除这条草稿？")) {
                    onDeleteDraft(draft.draft_id);
                  }
                }}
              >
                删除
              </Button>
            </div>
          </li>
          );
        })}
      </ul>
    </div>
  );
}
