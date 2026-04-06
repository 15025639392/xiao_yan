import type { Goal } from "../../lib/api";
import { renderGoalStatus } from "./goalsUtils";

type GoalItemProps = {
  goal: Goal;
  onAbandonClick: (goalId: string, goalTitle: string) => void;
  onCompleteClick: (goalId: string, goalTitle: string) => void;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  onDecomposeGoal: (goalId: string) => void;
  loadingDecompose: Set<string>;
};

export function GoalItem({
  goal,
  onAbandonClick,
  onCompleteClick,
  onUpdateGoalStatus,
  onDecomposeGoal,
  loadingDecompose,
}: GoalItemProps) {
  return (
    <li className="goal-card">
      <div className="goal-card__top">
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="goal-card__title" title={goal.title}>
            {goal.title}
          </p>
          <div className="goal-card__meta">
            {goal.chain_id ? <span className="goal-card__meta-item">链 {goal.chain_id}</span> : null}
            <span className="goal-card__meta-item">G{goal.generation ?? 0}</span>
            {goal.source ? (
              <span className="goal-card__meta-item" title={goal.source}>
                📌
              </span>
            ) : null}
          </div>
        </div>
        <span className={`status-badge status-badge--${goal.status}`}>{renderGoalStatus(goal.status)}</span>
      </div>

      {goal.generation === 0 && goal.status === "active" ? (
        <div
          style={{
            marginTop: "var(--space-2)",
            paddingTop: "var(--space-2)",
            borderTop: "1px solid var(--border-default)",
          }}
        >
          <button
            className="btn btn--secondary btn--sm"
            type="button"
            onClick={() => onDecomposeGoal(goal.id)}
            disabled={loadingDecompose.has(goal.id)}
            style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)" }}
          >
            {loadingDecompose.has(goal.id) ? "⏳ 分解中..." : "🔧 分解任务"}
          </button>
        </div>
      ) : null}

      {goal.status !== "completed" && goal.status !== "abandoned" ? (
        <div className="goal-card__actions">
          {goal.status === "active" ? (
            <button
              className="btn btn--secondary btn--sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "paused")}
            >
              暂停
            </button>
          ) : null}

          {goal.status === "paused" ? (
            <button
              className="btn btn--secondary btn--sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "active")}
            >
              恢复
            </button>
          ) : null}

          <button className="btn btn--primary btn--sm" type="button" onClick={() => onCompleteClick(goal.id, goal.title)}>
            完成
          </button>

          <button className="btn btn--danger btn--sm" type="button" onClick={() => onAbandonClick(goal.id, goal.title)}>
            放弃
          </button>
        </div>
      ) : null}
    </li>
  );
}
