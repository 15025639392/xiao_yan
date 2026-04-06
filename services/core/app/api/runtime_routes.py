from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.deps import (
    get_goal_repository,
    get_memory_repository,
    get_morning_plan_draft_generator,
    get_morning_plan_planner,
    get_state_store,
)
from app.domain.models import FocusMode, WakeMode
from app.goals.models import Goal
from app.goals.models import GoalStatus, GoalStatusUpdate
from app.goals.repository import GoalRepository
from app.llm.schemas import ChatHistoryMessage, ChatHistoryResponse
from app.memory.repository import MemoryRepository
from app.planning.morning_plan import MorningPlanDraftGenerator, MorningPlanPlanner
from app.runtime import StateStore
from app.runtime_ext.bootstrap import deduplicate_entries, ensure_realtime_hub_initialized, ensure_runtime_initialized


def build_runtime_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.websocket("/ws/app")
    async def app_realtime(websocket: WebSocket) -> None:
        ensure_runtime_initialized(websocket.app)
        ensure_realtime_hub_initialized(websocket.app)
        hub = websocket.app.state.realtime_hub
        await hub.connect(websocket)

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect(websocket)

    @router.get("/state")
    def get_state(state_store: StateStore = Depends(get_state_store)) -> dict:
        return state_store.get().model_dump()

    @router.get("/messages")
    def get_messages(memory_repository: MemoryRepository = Depends(get_memory_repository)) -> ChatHistoryResponse:
        recent_events = list(reversed(memory_repository.list_recent(limit=20)))
        messages = [
            ChatHistoryMessage(
                id=event.entry_id,
                role=event.role,
                content=event.content,
                created_at=event.created_at.isoformat() if event.created_at else None,
                session_id=event.session_id,
            )
            for event in recent_events
            if event.kind == "chat" and event.role in {"user", "assistant"}
        ]
        return ChatHistoryResponse(messages=messages)

    @router.get("/autobio")
    def get_autobio(memory_repository: MemoryRepository = Depends(get_memory_repository)) -> dict[str, list[str]]:
        recent_events = list(reversed(memory_repository.list_recent(limit=20)))
        entries = [event.content for event in recent_events if event.kind == "autobio"]
        return {"entries": deduplicate_entries(entries)}

    @router.get("/goals")
    def get_goals(goal_repository: GoalRepository = Depends(get_goal_repository)) -> dict[str, list[Goal]]:
        return {"goals": goal_repository.list_goals()}

    def _rebuild_today_plan_for_goal(
        goal: Goal,
        planner: MorningPlanPlanner,
        draft_generator: MorningPlanDraftGenerator | None = None,
        recent_autobio: str | None = None,
    ) -> dict:
        return {
            "focus_mode": FocusMode.MORNING_PLAN,
            "today_plan": planner.build_plan(
                goal,
                draft_generator=draft_generator,
                recent_autobio=recent_autobio,
            ),
        }

    @router.post("/goals/{goal_id}/status")
    def update_goal_status(
        goal_id: str,
        request: GoalStatusUpdate,
        goal_repository: GoalRepository = Depends(get_goal_repository),
        state_store: StateStore = Depends(get_state_store),
        planner: MorningPlanPlanner = Depends(get_morning_plan_planner),
        draft_generator: MorningPlanDraftGenerator | None = Depends(get_morning_plan_draft_generator),
    ) -> Goal:
        goal = goal_repository.update_status(goal_id, request.status)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")

        state = state_store.get()
        if request.status in {GoalStatus.PAUSED, GoalStatus.ABANDONED} and goal_id in state.active_goal_ids:
            remaining_goal_ids = [item for item in state.active_goal_ids if item != goal_id]
            next_focus_goal = next(
                (item for item in goal_repository.list_active_goals() if item.id in remaining_goal_ids),
                None,
            )
            state_store.set(
                state.model_copy(
                    update={
                        "active_goal_ids": remaining_goal_ids,
                        **(
                            _rebuild_today_plan_for_goal(next_focus_goal, planner, draft_generator=draft_generator)
                            if next_focus_goal is not None and state.mode == WakeMode.AWAKE
                            else {
                                "today_plan": (
                                    None
                                    if state.today_plan is not None and state.today_plan.goal_id == goal_id
                                    else state.today_plan
                                ),
                                "focus_mode": FocusMode.AUTONOMY if state.mode == WakeMode.AWAKE else FocusMode.SLEEPING,
                            }
                        ),
                    }
                )
            )
        elif request.status == GoalStatus.ACTIVE and goal_id not in state.active_goal_ids:
            next_active_goal_ids = [goal_id, *[item for item in state.active_goal_ids if item != goal_id]]
            state_store.set(
                state.model_copy(
                    update={
                        "active_goal_ids": next_active_goal_ids,
                        **(
                            _rebuild_today_plan_for_goal(goal, planner, draft_generator=draft_generator)
                            if state.mode == WakeMode.AWAKE
                            else {
                                "focus_mode": FocusMode.SLEEPING,
                                "today_plan": state.today_plan,
                            }
                        ),
                    }
                )
            )

        return goal

    return router
