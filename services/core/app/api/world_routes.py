from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_goal_repository,
    get_memory_repository,
    get_morning_plan_draft_generator,
    get_morning_plan_planner,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)
from app.domain.models import FocusMode, WakeMode
from app.goals.models import Goal
from app.goals.repository import GoalRepository
from app.memory.repository import MemoryRepository
from app.planning.morning_plan import MorningPlanDraftGenerator, MorningPlanPlanner
from app.runtime import StateStore
from app.runtime_ext.bootstrap import build_world_state, find_recent_autobio
from app.usecases.lifecycle import wake_up
from app.world.repository import WorldRepository
from app.world.service import WorldStateService


def build_world_router() -> APIRouter:
    router = APIRouter()

    @router.get("/world")
    def get_world(
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        world_repository: WorldRepository = Depends(get_world_repository),
        world_state_service: WorldStateService = Depends(get_world_state_service),
    ) -> dict:
        world_state = build_world_state(
            state_store,
            goal_repository,
            memory_repository,
            world_repository,
            world_state_service,
        )
        return world_state.model_dump()

    def _select_wake_goal(goal_repository: GoalRepository, recent_autobio: str | None) -> Goal | None:
        active_goals = goal_repository.list_active_goals()
        if not active_goals:
            return None
        if recent_autobio is None:
            return active_goals[0]
        chained_goals = [goal for goal in active_goals if goal.chain_id is not None]
        if not chained_goals:
            return active_goals[0]
        return sorted(
            chained_goals,
            key=lambda goal: (goal.generation, goal.updated_at, goal.created_at),
            reverse=True,
        )[0]

    @router.post("/lifecycle/wake")
    def wake(
        state_store: StateStore = Depends(get_state_store),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        planner: MorningPlanPlanner = Depends(get_morning_plan_planner),
        draft_generator: MorningPlanDraftGenerator | None = Depends(get_morning_plan_draft_generator),
    ) -> dict:
        current_state = state_store.get()
        recent_autobio = find_recent_autobio(memory_repository)
        selected_goal = _select_wake_goal(goal_repository, recent_autobio)
        waking_state = wake_up(recent_autobio=recent_autobio).model_copy(
            update={"self_programming_job": current_state.self_programming_job}
        )

        if selected_goal is not None:
            today_plan = planner.build_plan(
                selected_goal,
                draft_generator=draft_generator,
                recent_autobio=recent_autobio,
            )
            waking_state = waking_state.model_copy(
                update={
                    "active_goal_ids": [selected_goal.id],
                    "focus_mode": FocusMode.MORNING_PLAN,
                    "today_plan": today_plan,
                    "current_thought": (
                        f"{waking_state.current_thought} 今天想先接着“{selected_goal.title}”。"
                        f"{planner.build_plan_summary_from_plan(today_plan)}"
                    ),
                }
            )

        return state_store.set(waking_state).model_dump()

    @router.post("/lifecycle/sleep")
    def sleep(state_store: StateStore = Depends(get_state_store)) -> dict:
        current_state = state_store.get()
        sleeping_state = current_state.model_copy(
            update={
                "mode": WakeMode.SLEEPING,
                "focus_mode": FocusMode.SLEEPING,
                "current_thought": None,
                "active_goal_ids": [],
                "today_plan": None,
                "last_action": None,
            }
        )
        return state_store.set(sleeping_state).model_dump()

    return router
