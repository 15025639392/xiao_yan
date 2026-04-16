import { Button, Textarea } from "../ui";

type ApprovalActionsProps = {
  showRejectForm: boolean;
  decisioning: boolean;
  rejectReason: string;
  onApprove: () => void;
  onOpenRejectForm: () => void;
  onRejectReasonChange: (value: string) => void;
  onCancelReject: () => void;
  onReject: () => void;
};

export function ApprovalActions({
  showRejectForm,
  decisioning,
  rejectReason,
  onApprove,
  onOpenRejectForm,
  onRejectReasonChange,
  onCancelReject,
  onReject,
}: ApprovalActionsProps) {
  return (
    <div className="approval-actions">
      {!showRejectForm ? (
        <>
          <Button type="button" variant="default" size="lg" disabled={decisioning} onClick={onApprove} style={{ flex: 2 }}>
            {decisioning ? "⏳ 处理中..." : "✅ 批准应用"}
          </Button>
          <Button type="button" variant="secondary" size="sm" disabled={decisioning} onClick={onOpenRejectForm} style={{ flex: 1 }}>
            🚫 拒绝
          </Button>
        </>
      ) : (
        <div className="approval-reject-form">
          <label className="approval-reject-form__label" htmlFor="reject-reason">
            请填写拒绝原因（帮助数字人学习）：
          </label>
          <Textarea
            id="reject-reason"
            className="approval-reject-form__textarea"
            value={rejectReason}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            placeholder="例如：这个修改范围太大了，我想先看看具体改动..."
            rows={3}
            autoFocus
          />
          <div className="approval-reject-form__actions">
            <Button type="button" variant="secondary" size="sm" onClick={onCancelReject} disabled={decisioning}>
              返回
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={onReject}
              disabled={decisioning || !rejectReason.trim()}
            >
              确认拒绝
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
