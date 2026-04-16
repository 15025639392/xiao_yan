import type { Goal, TodayPlan } from "../../lib/api";
import { Button } from "../ui";

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
