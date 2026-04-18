from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import BeingState, TodayPlanStepStatus
from app.goals.models import Goal
from app.goals.repository import GoalRepository


@dataclass(slots=True)
class FocusContext:
    goal_title: str
    source_kind: str
    source_label: str
    reason_kind: str
    reason_label: str

    def render_for_prompt(self) -> str:
        return f"当前焦点来自{self.source_label}，之所以还在推进，是因为{self.reason_label}。"

    def to_payload(self) -> dict[str, str]:
        return {
            "goal_title": self.goal_title,
            "source_kind": self.source_kind,
            "source_label": self.source_label,
            "reason_kind": self.reason_kind,
            "reason_label": self.reason_label,
            "prompt_summary": self.render_for_prompt(),
        }


def build_focus_context(
    *,
    state: BeingState,
    goal_repository: GoalRepository,
) -> FocusContext | None:
    if not state.active_goal_ids:
        if state.today_plan is None:
            return None
        return FocusContext(
            goal_title=state.today_plan.goal_title,
            source_kind="today_plan_retained",
            source_label="今天这条还留在眼前的计划",
            reason_kind=_plan_reason_kind(state.today_plan),
            reason_label=_plan_reason(state.today_plan),
        )

    focus_goal = goal_repository.get_goal(state.active_goal_ids[0])
    if focus_goal is None:
        if state.today_plan is None:
            return None
        return FocusContext(
            goal_title=state.today_plan.goal_title,
            source_kind="today_plan_fallback",
            source_label="今天这条还接着在延续的计划",
            reason_kind=_plan_reason_kind(state.today_plan),
            reason_label=_plan_reason(state.today_plan),
        )

    source_kind, source_label = _source_descriptor(focus_goal)
    reason_kind, reason_label = _reason_descriptor(state, focus_goal)
    return FocusContext(
        goal_title=focus_goal.title,
        source_kind=source_kind,
        source_label=source_label,
        reason_kind=reason_kind,
        reason_label=reason_label,
    )


def _source_descriptor(goal: Goal) -> tuple[str, str]:
    if goal.admission is not None and goal.admission.deferred_retries > 0:
        return "deferred_goal_reactivated", "之前放过一阵子、现在又重新提上来的事"
    if goal.chain_id is not None or goal.parent_goal_id is not None or goal.generation > 0:
        return "goal_chain", "她一直接着往下推进的这条线"
    if goal.admission is not None and goal.admission.reason == "user_score":
        return "user_topic_goal", "刚接住你这轮话题的事"
    if goal.source:
        return "retained_goal", "之前已经在推进、现在还接着在做的事"
    return "active_goal", "她手上现在还挂着的事"


def _reason_descriptor(state: BeingState, goal: Goal) -> tuple[str, str]:
    today_plan = state.today_plan
    if today_plan is not None and today_plan.goal_id == goal.id:
        return _plan_reason_kind(today_plan), _plan_reason(today_plan)
    if goal.chain_id is not None and goal.generation >= 2:
        return "goal_chain_closing", f"这条线已经推到第{goal.generation + 1}步了，现在主要是在收尾"
    if goal.chain_id is not None:
        return "goal_chain_continuing", f"这条线已经推到第{goal.generation + 1}步了，还会继续往下走"
    return "goal_still_active", "这件事还没完成，也还没有暂停或放下"


def _plan_reason_kind(today_plan) -> str:
    pending_steps = [
        step for step in today_plan.steps if step.status == TodayPlanStepStatus.PENDING
    ]
    if pending_steps:
        return "today_plan_pending"
    return "today_plan_warm_closure"


def _plan_reason(today_plan) -> str:
    pending_steps = [
        step for step in today_plan.steps if step.status == TodayPlanStepStatus.PENDING
    ]
    if pending_steps:
        return f"今天这条还剩 {len(pending_steps)} 步没做完"
    return "今天这条刚做完，但那股收尾的劲还在"
