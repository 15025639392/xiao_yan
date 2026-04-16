import { Button, StatusBadge } from "../ui";

type GoalsHeaderActionsProps = {
  goalsCount: number;
  executionStatsSupported: boolean;
  showExecutionPanel: boolean;
  onToggleExecutionPanel: () => void;
};

export function GoalsHeaderActions({
  goalsCount,
  executionStatsSupported,
  showExecutionPanel,
  onToggleExecutionPanel,
}: GoalsHeaderActionsProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      {executionStatsSupported ? (
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={onToggleExecutionPanel}
          style={{ fontSize: "0.75rem" }}
        >
          {showExecutionPanel ? "📊 隐藏统计" : "📊 执行统计"}
        </Button>
      ) : null}
      <StatusBadge tone="awake">{goalsCount} 个目标</StatusBadge>
    </div>
  );
}
