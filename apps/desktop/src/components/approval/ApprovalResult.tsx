type ApprovalResultProps = {
  result: "approved" | "rejected";
  targetArea: string;
  rejectReason: string;
  approvalReason?: string | null;
};

export function ApprovalResult({ result, targetArea, rejectReason, approvalReason }: ApprovalResultProps) {
  return (
    <section className={`approval-panel approval-panel--${result}`}>
      <div className="approval-panel__header">
        <span className="approval-panel__icon">{result === "approved" ? "✅" : "🚫"}</span>
        <h3 className="approval-panel__title">{result === "approved" ? "已批准" : "已拒绝"}</h3>
      </div>
      <div className="approval-panel__body">
        <p>
          {result === "approved"
            ? `自我编程方案「${targetArea}」已被批准，正在继续执行验证流程...`
            : `自我编程方案「${targetArea}」已被拒绝。${approvalReason ?? rejectReason}`}
        </p>
      </div>
    </section>
  );
}
