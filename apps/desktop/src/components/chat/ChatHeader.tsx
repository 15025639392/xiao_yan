import type { Goal, TodayPlan } from "../../lib/api";

type ChatHeaderProps = {
  focusGoalTitle?: string | null;
  todayPlan?: TodayPlan | null;
  activeGoals?: Goal[];
  onCompleteGoal?: (goalId: string) => Promise<void>;
  onToggleConfig: () => void;
};

export function ChatHeader({
  focusGoalTitle,
  todayPlan,
  activeGoals,
  onCompleteGoal,
  onToggleConfig,
}: ChatHeaderProps) {
  return (
    <header className="chat-page__header">
      <div className="chat-page__header-info">
        <h2 className="chat-page__title">{focusGoalTitle ?? "自由对话"}</h2>
        {todayPlan ? (
          <span className="chat-page__subtitle">
            今日计划: {todayPlan.steps.filter((step) => step.status === "completed").length}/{todayPlan.steps.length} 完成
          </span>
        ) : null}
      </div>
      <div className="chat-page__header-actions">
        <button className="chat-page__action-btn" onClick={onToggleConfig} type="button" title="配置">
          ⚙️ 配置
        </button>
        {todayPlan?.steps.some((step) => step.status === "pending") && activeGoals && activeGoals[0] && onCompleteGoal ? (
          <button className="chat-page__action-btn" onClick={() => void onCompleteGoal(activeGoals[0].id)} type="button">
            完成目标
          </button>
        ) : null}
      </div>
    </header>
  );
}
