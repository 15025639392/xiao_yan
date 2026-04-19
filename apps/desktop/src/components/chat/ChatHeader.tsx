import type { FocusContext, FocusEffort, FocusSubject } from "../../lib/api";
import { getFocusEffortTitle } from "../../lib/focusEffortPresentation";
import { getFocusContextBadge, getFocusContextLines } from "../../lib/focusContextPresentation";
import { Button, StatusBadge } from "../ui";

type ChatHeaderProps = {
  focusGoalTitle?: string | null;
  focusContext?: FocusContext | null;
  focusSubject?: FocusSubject | null;
  focusEffort?: FocusEffort | null;
  onToggleConfig: () => void;
};

export function ChatHeader({
  focusGoalTitle,
  focusContext,
  focusSubject,
  focusEffort,
  onToggleConfig,
}: ChatHeaderProps) {
  const focusContextLines = getFocusContextLines(focusContext);
  const focusStatusBadge = getFocusContextBadge(focusContext);
  const focusEffortTitle = getFocusEffortTitle(focusEffort);
  const focusLeadLine = focusSubject?.why_now?.trim() || focusContextLines[0] || null;

  return (
    <header className="chat-page__header">
      <div className="chat-page__header-info">
        <div className="chat-page__title-row">
          <h2 className="chat-page__title">{focusGoalTitle ?? "自由对话"}</h2>
          {focusStatusBadge ? <StatusBadge tone={focusStatusBadge.tone}>{focusStatusBadge.label}</StatusBadge> : null}
        </div>
        {focusLeadLine ? <span className="chat-page__subtitle">{focusLeadLine}</span> : null}
        {focusEffortTitle && focusEffort ? (
          <span className="chat-page__subtitle">
            {focusEffortTitle}: {focusEffort.did_what}
          </span>
        ) : null}
      </div>
      <div className="chat-page__header-actions">
        <Button className="chat-page__action-btn" variant="secondary" onClick={onToggleConfig} type="button" title="对话设置">
          ⚙️ 对话设置
        </Button>
      </div>
    </header>
  );
}
