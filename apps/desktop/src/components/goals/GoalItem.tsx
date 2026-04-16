import type { Goal, RelationshipSummary } from "../../lib/api";
import { Button, StatusBadge } from "../ui";
import { getGoalAdmissionDisplay } from "./goalAdmissionMeta";
import { renderGoalStatus } from "./goalsUtils";
import { getGoalSourceMeta } from "./goalSourceMeta";
import { getGoalRelationshipHints } from "./relationshipGoalHints";

type GoalItemProps = {
  goal: Goal;
  onAbandonClick: (goalId: string, goalTitle: string) => void;
  onCompleteClick: (goalId: string, goalTitle: string) => void;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  onDecomposeGoal: (goalId: string) => void;
  loadingDecompose: Set<string>;
  relationship: RelationshipSummary | null;
};

export function GoalItem({
  goal,
  onAbandonClick,
  onCompleteClick,
  onUpdateGoalStatus,
  onDecomposeGoal,
  loadingDecompose,
  relationship,
}: GoalItemProps) {
  const admissionDisplay = getGoalAdmissionDisplay(goal);
  const sourceMeta = getGoalSourceMeta(goal);
  const relationshipHints = getGoalRelationshipHints(goal, relationship);

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
          </div>
        </div>
        <StatusBadge tone={goal.status}>{renderGoalStatus(goal.status)}</StatusBadge>
      </div>

      <section className={`goal-card__source goal-card__source--${sourceMeta.tone}`} aria-label="目标来历">
        <div className="goal-card__source-head">
          <span className="goal-card__source-chip">{sourceMeta.label}</span>
          <span className="goal-card__source-summary">{sourceMeta.summary}</span>
        </div>
        {sourceMeta.context ? (
          <div className="goal-card__source-context">
            <span className="goal-card__source-context-label">{sourceMeta.contextLabel}</span>
            <span className="goal-card__source-context-text">{sourceMeta.context}</span>
          </div>
        ) : null}
      </section>

      {admissionDisplay ? (
        <section className={`goal-card__admission goal-card__admission--${admissionDisplay.tone}`} aria-label="准入判断">
          <div className="goal-card__admission-head">
            <span className="goal-card__admission-chip">{admissionDisplay.badge}</span>
            <span className="goal-card__admission-score">{admissionDisplay.scoreText}</span>
          </div>
          <div className="goal-card__admission-summary">{admissionDisplay.summary}</div>
          {admissionDisplay.trajectoryText ? (
            <div className="goal-card__admission-trajectory">{admissionDisplay.trajectoryText}</div>
          ) : null}
        </section>
      ) : null}

      {relationshipHints.length > 0 ? (
        <section className="goal-card__relationship" aria-label="关系提示">
          <span className="goal-card__relationship-title">关系提示</span>
          <div className="goal-card__relationship-list">
            {relationshipHints.map((hint) => (
              <div key={`${hint.label}:${hint.reason}`} className={`goal-card__relationship-item goal-card__relationship-item--${hint.tone}`}>
                <span className="goal-card__relationship-chip">{hint.label}</span>
                <span className="goal-card__relationship-text">{hint.reason}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {goal.generation === 0 && goal.status === "active" ? (
        <div
          style={{
            marginTop: "var(--space-2)",
            paddingTop: "var(--space-2)",
            borderTop: "1px solid var(--border-default)",
          }}
        >
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={() => onDecomposeGoal(goal.id)}
            disabled={loadingDecompose.has(goal.id)}
            style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)" }}
          >
            {loadingDecompose.has(goal.id) ? "⏳ 分解中..." : "🔧 分解任务"}
          </Button>
        </div>
      ) : null}

      {goal.status !== "completed" && goal.status !== "abandoned" ? (
        <div className="goal-card__actions">
          {goal.status === "active" ? (
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "paused")}
            >
              暂停
            </Button>
          ) : null}

          {goal.status === "paused" ? (
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "active")}
            >
              恢复
            </Button>
          ) : null}

          <Button variant="default" size="sm" type="button" onClick={() => onCompleteClick(goal.id, goal.title)}>
            完成
          </Button>

          <Button variant="destructive" size="sm" type="button" onClick={() => onAbandonClick(goal.id, goal.title)}>
            放弃
          </Button>
        </div>
      ) : null}
    </li>
  );
}
