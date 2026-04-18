from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agent.loop_helpers import (
    build_chain_consolidation,
    build_goal_completion,
    build_goal_focus,
    build_today_plan_step_focus,
)
from app.domain.models import FocusMode, TodayPlan, TodayPlanStepKind, TodayPlanStepStatus
from app.focus.effort import (
    chain_advanced_effort,
    command_effort,
    consolidate_effort,
    focus_adopted_effort,
    focus_hold_effort,
    focus_resumed_effort,
    goal_completed_effort,
    plan_action_effort,
    plan_step_effort,
)
from app.goals.models import Goal


def goal_command_update(
    *,
    goal_id: str | None,
    goal_title: str,
    action_summary: str,
    result: Any,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": action_summary,
        "focus_effort": command_effort(
            goal_id=goal_id,
            goal_title=goal_title,
            command=result.command,
            output=result.output,
            now=now,
        ),
        "last_action": result,
    }


def goal_hold_update(
    *,
    goal_id: str | None,
    goal_title: str,
    world_state,
    chain_progress: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": build_goal_focus(goal_title, now, world_state, chain_progress),
        "focus_effort": focus_hold_effort(
            goal_id=goal_id,
            goal_title=goal_title,
            now=now,
        ),
    }


def goal_consolidate_update(
    *,
    goal_id: str | None,
    goal_title: str,
    world_state,
    chain_progress: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": build_chain_consolidation(
            goal_title,
            now,
            world_state,
            chain_progress,
        ),
        "focus_effort": consolidate_effort(
            goal_id=goal_id,
            goal_title=goal_title,
            now=now,
        ),
    }


def adopted_goal_update(
    *,
    goal: Goal,
    proactive_message: str,
    source_content: str,
    now: datetime,
) -> dict[str, object]:
    return {
        "active_goal_ids": [goal.id],
        "current_thought": proactive_message,
        "focus_effort": focus_adopted_effort(
            goal_id=goal.id,
            goal_title=goal.title,
            now=now,
        ),
        "last_proactive_source": source_content,
        "last_proactive_at": now,
    }


def resumed_goal_update(
    *,
    goal: Goal,
    proactive_message: str,
    source_content: str,
    now: datetime,
) -> dict[str, object]:
    return {
        "active_goal_ids": [goal.id],
        "current_thought": proactive_message,
        "focus_effort": focus_resumed_effort(
            goal_id=goal.id,
            goal_title=goal.title,
            now=now,
        ),
        "last_proactive_source": source_content,
        "last_proactive_at": now,
    }


def chain_advanced_update(
    *,
    goal: Goal,
    thought: str,
    source_content: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "active_goal_ids": [goal.id],
        "current_thought": thought,
        "focus_effort": chain_advanced_effort(
            goal_id=goal.id,
            goal_title=goal.title,
            step=goal.generation + 1,
            now=now,
        ),
        "last_proactive_source": source_content,
        "last_proactive_at": now,
    }


def completed_goal_update(
    *,
    goal: Goal,
    next_goal: Goal | None,
    active_goal_ids: list[str],
    world_state,
    chain_progress: str | None,
    last_proactive_source: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "active_goal_ids": [next_goal.id] if next_goal is not None else active_goal_ids,
        "focus_mode": FocusMode.AUTONOMY,
        "today_plan": None,
        "current_thought": build_goal_completion(
            goal.title,
            now,
            world_state,
            chain_progress=chain_progress,
            next_goal_title=None if next_goal is None else next_goal.title,
        ),
        "focus_effort": goal_completed_effort(
            goal_title=goal.title,
            next_goal_id=None if next_goal is None else next_goal.id,
            next_goal_title=None if next_goal is None else next_goal.title,
            now=now,
        ),
        "last_proactive_source": goal.source or last_proactive_source,
        "last_proactive_at": now,
    }


def dropped_focus_update(
    *,
    active_goal_ids: list[str],
    today_plan: TodayPlan | None,
    focus_mode: FocusMode,
) -> dict[str, object]:
    return {
        "active_goal_ids": active_goal_ids,
        "today_plan": today_plan,
        "focus_effort": None,
        "focus_mode": focus_mode,
    }


def plan_step_updates(
    *,
    today_plan: TodayPlan,
    next_step_content: str,
    next_steps,
    next_focus_mode: FocusMode,
    now: datetime,
    world_state,
) -> dict[str, object]:
    updates: dict[str, object] = {
        "focus_mode": next_focus_mode,
        "today_plan": today_plan.model_copy(update={"steps": next_steps}),
    }
    updates["current_thought"] = build_today_plan_step_focus(
        today_plan.goal_title,
        next_step_content,
        now,
        world_state,
    )
    completed_steps = sum(
        step.status == TodayPlanStepStatus.COMPLETED for step in next_steps
    )
    updates["focus_effort"] = plan_step_effort(
        goal_id=today_plan.goal_id,
        goal_title=today_plan.goal_title,
        step_content=next_step_content,
        completed_steps=completed_steps,
        total_steps=len(next_steps),
        plan_done=next_focus_mode == FocusMode.AUTONOMY,
        now=now,
    )
    return updates


def plan_action_updates(
    *,
    today_plan: TodayPlan,
    next_step_content: str,
    next_steps,
    next_focus_mode: FocusMode,
    result: Any,
    action_summary: str,
    now: datetime,
) -> dict[str, object]:
    return {
        "focus_mode": next_focus_mode,
        "today_plan": today_plan.model_copy(update={"steps": next_steps}),
        "current_thought": action_summary,
        "focus_effort": plan_action_effort(
            goal_id=today_plan.goal_id,
            goal_title=today_plan.goal_title,
            step_content=next_step_content,
            command=result.command,
            output=result.output,
            now=now,
        ),
        "last_action": result,
    }
