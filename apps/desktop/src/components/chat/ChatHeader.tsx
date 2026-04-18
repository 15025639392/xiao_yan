import type { FocusContext, FocusEffort, Goal, TodayPlan } from "../../lib/api";
import { getFocusEffortTitle } from "../../lib/focusEffortPresentation";
import { getFocusContextBadge, getFocusContextLines } from "../../lib/focusContextPresentation";
import { Button, StatusBadge } from "../ui";

type ChatHeaderProps = {
  focusGoalTitle?: string | null;
  focusContext?: FocusContext | null;
  focusTransitionHint?: string | null;
  focusContextSummary?: string | null;
  focusEffort?: FocusEffort | null;
  todayPlan?: TodayPlan | null;
  activeGoals?: Goal[];
  onCompleteGoal?: (goalId: string) => Promise<void>;
  onToggleConfig: () => void;
};

export function ChatHeader({
  focusGoalTitle,
  focusContext,
  focusTransitionHint,
  focusContextSummary,
  focusEffort,
  todayPlan,
  activeGoals,
  onCompleteGoal,
  onToggleConfig,
}: ChatHeaderProps) {
  const focusContextLines = getFocusContextLines(focusContext, focusContextSummary);
  const focusStatusBadge = getFocusContextBadge(focusContext);
  const focusEffortTitle = getFocusEffortTitle(focusEffort);

  return (
    <header className="chat-page__header">
      <div className="chat-page__header-info">
        <div className="chat-page__title-row">
          <h2 className="chat-page__title">{focusGoalTitle ?? "自由对话"}</h2>
          {focusStatusBadge ? <StatusBadge tone={focusStatusBadge.tone}>{focusStatusBadge.label}</StatusBadge> : null}
        </div>
        {focusContextLines.map((line) => (
          <span key={line} className="chat-page__subtitle">
            {line}
          </span>
        ))}
        {focusTransitionHint ? <span className="chat-page__subtitle chat-page__subtitle--accent">{focusTransitionHint}</span> : null}
        {focusEffortTitle && focusEffort ? (
          <span className="chat-page__subtitle">
            {focusEffortTitle}: {focusEffort.did_what}
          </span>
        ) : null}
        {todayPlan ? (
          <span className="chat-page__subtitle">
            今日计划: {todayPlan.steps.filter((step) => step.status === "completed").length}/{todayPlan.steps.length} 完成
          </span>
        ) : null}
      </div>
      <div className="chat-page__header-actions">
        <Button className="chat-page__action-btn" variant="secondary" onClick={onToggleConfig} type="button" title="配置">
          ⚙️ 配置
        </Button>
        {todayPlan?.steps.some((step) => step.status === "pending") && activeGoals && activeGoals[0] && onCompleteGoal ? (
          <Button className="chat-page__action-btn" variant="secondary" onClick={() => void onCompleteGoal(activeGoals[0].id)} type="button">
            完成目标
          </Button>
        ) : null}
      </div>
    </header>
  );
}
