import { StatusBadge } from "../ui";

type GoalsHeaderActionsProps = {
  goalsCount: number;
  showExecutionPanel: boolean;
  onToggleExecutionPanel: () => void;
};

export function GoalsHeaderActions({
  goalsCount,
  showExecutionPanel,
  onToggleExecutionPanel,
}: GoalsHeaderActionsProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <button
        className="btn btn--secondary btn--sm"
        type="button"
        onClick={onToggleExecutionPanel}
        style={{ fontSize: "0.75rem" }}
      >
        {showExecutionPanel ? "📊 隐藏统计" : "📊 执行统计"}
      </button>
      <StatusBadge tone="awake">{goalsCount} 个目标</StatusBadge>
    </div>
  );
}
