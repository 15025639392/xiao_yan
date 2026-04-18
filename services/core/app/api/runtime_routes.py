from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from app.api.deps import (
    get_goal_admission_service,
    get_goal_repository,
    get_memory_repository,
    get_mempalace_adapter,
    get_morning_plan_draft_generator,
    get_morning_plan_planner,
    get_persona_service,
    get_state_store,
)
from app.domain.models import FocusMode, WakeMode
from app.focus.effort import (
    manual_abandon_effort,
    manual_complete_effort,
    manual_focus_switch_effort,
    manual_pause_effort,
)
from app.focus.selection import select_focus_goal
from app.goals.admission import GoalAdmissionService
from app.goals.models import Goal
from app.goals.models import GoalStatus, GoalStatusUpdate
from app.goals.repository import GoalRepository
from app.llm.schemas import ChatHistoryMessage, ChatHistoryResponse
from app.memory.repository import MemoryRepository
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.persona.service import PersonaService
from app.planning.morning_plan import MorningPlanDraftGenerator, MorningPlanPlanner
from app.runtime import StateStore
from app.runtime_ext.bootstrap import ensure_realtime_hub_initialized, ensure_runtime_initialized
from app.runtime_ext.snapshot import build_public_state_payload, deduplicate_entries
from app.runtime_ext.runtime_config import get_runtime_config


def build_runtime_router() -> APIRouter:
    router = APIRouter()
    DEFAULT_CHAT_MESSAGES_LIMIT = 80

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/environment/mac-console")
    def get_mac_console_environment_status(request: Request) -> dict:
        ensure_runtime_initialized(request.app)
        return (
            getattr(request.app.state, "mac_console_bootstrap_status", None)
            or {
                "state": "unknown",
                "healthy": False,
                "platform": "unknown",
                "enabled": False,
                "attempted_autofix": False,
                "summary": "mac console bootstrap status is unavailable.",
                "checked_at": None,
                "script_path": None,
                "check_exit_code": None,
                "apply_exit_code": None,
            }
        )

    @router.websocket("/ws/app")
    async def app_realtime(websocket: WebSocket) -> None:
        ensure_runtime_initialized(websocket.app)
        ensure_realtime_hub_initialized(websocket.app)
        hub = websocket.app.state.realtime_hub
        connected = await hub.connect(websocket)
        if not connected:
            return

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.disconnect(websocket)

    @router.get("/state")
    def get_state(
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
    ) -> dict:
        return build_public_state_payload(state_store.get(), goal_repository)

    @router.get("/memory/backends")
    def get_memory_backends(
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
    ) -> dict:
        return {
            "chat_memory": mempalace_adapter.status_snapshot(),
        }

    @router.get("/messages")
    def get_messages(
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
        limit: int = Query(default=DEFAULT_CHAT_MESSAGES_LIMIT, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=200000),
    ) -> ChatHistoryResponse:
        recent_chat_events = mempalace_adapter.list_recent_chat_messages(limit=limit + 1, offset=offset)
        has_more = len(recent_chat_events) > limit
        page_events = recent_chat_events[:limit]
        messages = [
            ChatHistoryMessage(
                id=str(event.get("id") or ""),
                role=str(event.get("role") or "assistant"),
                content=str(event.get("content") or ""),
                created_at=event.get("created_at"),
                session_id=event.get("session_id"),
                request_key=event.get("request_key"),
                reasoning_session_id=event.get("reasoning_session_id"),
                reasoning_state=(event.get("reasoning_state") if isinstance(event.get("reasoning_state"), dict) else None),
            )
            for event in reversed(page_events)
            if isinstance(event, dict)
        ]
        next_offset = offset + len(page_events) if has_more else None
        return ChatHistoryResponse(
            messages=messages,
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=next_offset,
        )

    @router.get("/autobio")
    def get_autobio(memory_repository: MemoryRepository = Depends(get_memory_repository)) -> dict[str, list[str]]:
        recent_events = list(reversed(memory_repository.list_recent(limit=20)))
        entries = [event.content for event in recent_events if event.kind == "autobio"]
        return {"entries": deduplicate_entries(entries)}

    @router.get("/goals")
    def get_goals(goal_repository: GoalRepository = Depends(get_goal_repository)) -> dict[str, list[Goal]]:
        return {"goals": goal_repository.list_goals()}

    @router.get("/goals/admission/stats")
    def get_goal_admission_stats(
        admission_service: GoalAdmissionService = Depends(get_goal_admission_service),
    ) -> dict:
        config = get_runtime_config()
        return admission_service.get_stats(
            stability_warning_rate=config.goal_admission_stability_warning_rate,
            stability_danger_rate=config.goal_admission_stability_danger_rate,
        )

    @router.get("/goals/admission/candidates")
    def get_goal_admission_candidates(
        admission_service: GoalAdmissionService = Depends(get_goal_admission_service),
    ) -> dict:
        return admission_service.get_candidate_snapshot()

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

    def _goal_emotion_event_for(status: GoalStatus) -> str | None:
        mapping = {
            GoalStatus.ACTIVE: "progress",
            GoalStatus.PAUSED: "blocked",
            GoalStatus.COMPLETED: "completed",
            GoalStatus.ABANDONED: "abandoned",
        }
        return mapping.get(status)

    @router.post("/goals/{goal_id}/status")
    def update_goal_status(
        goal_id: str,
        request: GoalStatusUpdate,
        goal_repository: GoalRepository = Depends(get_goal_repository),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        planner: MorningPlanPlanner = Depends(get_morning_plan_planner),
        draft_generator: MorningPlanDraftGenerator | None = Depends(get_morning_plan_draft_generator),
    ) -> Goal:
        goal = goal_repository.update_status(goal_id, request.status)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")

        emotion_event = _goal_emotion_event_for(request.status)
        if emotion_event is not None:
            persona_service.infer_goal_emotion(emotion_event, goal.title)

        state = state_store.get()
        if request.status in {GoalStatus.PAUSED, GoalStatus.ABANDONED} and goal_id in state.active_goal_ids:
            remaining_goal_ids = [item for item in state.active_goal_ids if item != goal_id]
            next_focus_goal = select_focus_goal(
                goal_repository.list_active_goals(),
                preferred_goal_ids=remaining_goal_ids,
            )
            focus_effort = (
                manual_pause_effort(
                    goal_title=goal.title,
                    next_goal_id=None if next_focus_goal is None else next_focus_goal.id,
                    next_goal_title=None if next_focus_goal is None else next_focus_goal.title,
                )
                if request.status == GoalStatus.PAUSED
                else manual_abandon_effort(
                    goal_title=goal.title,
                    next_goal_id=None if next_focus_goal is None else next_focus_goal.id,
                    next_goal_title=None if next_focus_goal is None else next_focus_goal.title,
                )
            )
            state_store.set(
                state.model_copy(
                    update={
                        "active_goal_ids": remaining_goal_ids,
                        "focus_effort": focus_effort,
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
        elif request.status == GoalStatus.COMPLETED and goal_id in state.active_goal_ids:
            state_store.set(
                state.model_copy(
                    update={
                        "focus_effort": manual_complete_effort(
                            goal_id=goal.id,
                            goal_title=goal.title,
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
                        "focus_effort": manual_focus_switch_effort(
                            goal_id=goal.id,
                            goal_title=goal.title,
                        ),
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
