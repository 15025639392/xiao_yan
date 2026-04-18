from __future__ import annotations

from app.goals.models import Goal


def select_focus_goal(
    active_goals: list[Goal],
    *,
    recent_autobio: str | None = None,
    preferred_goal_ids: list[str] | None = None,
) -> Goal | None:
    if not active_goals:
        return None

    candidates = _filter_preferred_goals(active_goals, preferred_goal_ids)
    if not candidates:
        return None

    if recent_autobio is not None:
        chained_candidates = [goal for goal in candidates if goal.chain_id is not None]
        if chained_candidates:
            return sorted(
                chained_candidates,
                key=lambda goal: (goal.generation, goal.updated_at, goal.created_at),
                reverse=True,
            )[0]

    return candidates[0]


def _filter_preferred_goals(active_goals: list[Goal], preferred_goal_ids: list[str] | None) -> list[Goal]:
    if not preferred_goal_ids:
        return active_goals

    priority = {goal_id: index for index, goal_id in enumerate(preferred_goal_ids)}
    prioritized = [goal for goal in active_goals if goal.id in priority]
    return sorted(prioritized, key=lambda goal: priority[goal.id])
