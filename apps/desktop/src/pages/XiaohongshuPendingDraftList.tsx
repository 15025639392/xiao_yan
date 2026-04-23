import type { XhsWorkDomainState } from "../lib/apiRuntime";
import type { XiaohongshuCoverPreviewResponse } from "../lib/apiXiaohongshu";
import { Button } from "../components/ui";

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
        {drafts.map((draft) => (
          <li key={draft.draft_id} className="xhs-pending-item xhs-pending-item--editable">
            <div className="xhs-pending-item__actions">
              <span className="xhs-pending-item__status">{draft.status}</span>
              {drafts[0]?.draft_id === draft.draft_id ? (
                <span className="xhs-pending-item__status">下一条发布</span>
              ) : null}
            </div>
            <input
              className="xhs-pending-item__title-input"
              type="text"
              value={draftEdits[draft.draft_id]?.title ?? draft.title}
              onChange={(e) => onDraftEditChange(draft.draft_id, { title: e.target.value })}
            />
            <textarea
              className="xhs-pending-item__body-input"
              rows={3}
              value={draftEdits[draft.draft_id]?.body ?? draft.body}
              onChange={(e) => onDraftEditChange(draft.draft_id, { body: e.target.value })}
            />
            <div className="xhs-pending-item__cover">
              <div className="xhs-pending-item__cover-header">
                <strong>封面模板预览</strong>
                <div className="xhs-pending-item__cover-actions">
                  {(draftCoverPreviews[draft.draft_id]?.available_templates || Object.keys(COVER_TEMPLATE_LABELS)).map((templateName) => (
                    <Button
                      key={templateName}
                      variant={draftCoverPreviews[draft.draft_id]?.template_name === templateName ? "default" : "secondary"}
                      onClick={() => {
                        onSwitchDraftCoverTemplate(draft.draft_id, templateName);
                      }}
                      disabled={draftCoverLoading[draft.draft_id]}
                    >
                      {COVER_TEMPLATE_LABELS[templateName] || templateName}
                    </Button>
                  ))}
                </div>
              </div>
              {draftCoverLoading[draft.draft_id] ? <p className="xhs-history-empty">封面预览生成中...</p> : null}
              {draftCoverErrors[draft.draft_id] ? <p className="xhs-history-empty">{draftCoverErrors[draft.draft_id]}</p> : null}
              {draftCoverPreviews[draft.draft_id] ? (
                <div className="xhs-cover-preview">
                  <img
                    className="xhs-cover-preview__image"
                    src={draftCoverPreviews[draft.draft_id]?.image_data_url}
                    alt={`待发布草稿封面-${draftCoverPreviews[draft.draft_id]?.template_name}`}
                  />
                </div>
              ) : null}
            </div>
            <div className="xhs-pending-item__actions">
              <Button variant="outline" onClick={onSaveDrafts}>
                保存修改
              </Button>
              <Button
                variant="default"
                onClick={() => {
                  onPublishDraft(draft.draft_id);
                }}
                disabled={status === "reviewing"}
              >
                {publishMode === "auto" ? "优先自动发布" : "发布这条"}
              </Button>
              <Button
                variant="destructive"
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
        ))}
      </ul>
    </div>
  );
}
