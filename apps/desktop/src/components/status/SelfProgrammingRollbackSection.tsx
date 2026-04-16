import { Button } from "../ui";

type SelfProgrammingRollbackSectionProps = {
  canRollback: boolean;
  rollbackInfo?: string | null;
  rollingBack: boolean;
  rollbackOk: string | null;
  rollbackErr: string | null;
  onOpenConfirm: () => void;
};

export function SelfProgrammingRollbackSection({
  canRollback,
  rollbackInfo,
  rollingBack,
  rollbackOk,
  rollbackErr,
  onOpenConfirm,
}: SelfProgrammingRollbackSectionProps) {
  if (!canRollback && !rollbackInfo) {
    return null;
  }

  return (
    <div className="si-section si-section--rollback">
      {rollbackInfo ? (
        <div className="si-rollback-banner si-rollback-banner--info">
          <span>🔄</span>
          <span>{rollbackInfo}</span>
        </div>
      ) : null}
      {canRollback ? (
        <>
          <h4 className="si-section__title">回滚操作</h4>
          <p className="si-rollback-hint">此操作将恢复到修改前的文件状态（快照已保存）</p>
          <div className="si-rollback-actions">
            <Button type="button" variant="destructive" size="sm" disabled={rollingBack} onClick={onOpenConfirm}>
              {rollingBack ? "⏳ 回滚中..." : "↩️ 执行回滚"}
            </Button>
          </div>
          {rollbackOk ? <div className="si-rollback-banner si-rollback-banner--success">{rollbackOk}</div> : null}
          {rollbackErr ? <div className="si-rollback-banner si-rollback-banner--error">{rollbackErr}</div> : null}
        </>
      ) : null}
    </div>
  );
}
