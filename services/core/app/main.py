from collections.abc import Generator
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    get_goal_storage_path,
    get_memory_storage_path,
    get_state_storage_path,
    get_world_storage_path,
    is_morning_plan_llm_enabled,
)
from app.agent.loop import AutonomyLoop
from app.goals.models import Goal, GoalStatus, GoalStatusUpdate
from app.goals.repository import FileGoalRepository, GoalRepository
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResult,
)
from app.memory.models import MemoryEvent
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.persona.prompt_builder import build_chat_instructions
from app.planning.morning_plan import (
    LLMMorningPlanDraftGenerator,
    MorningPlanDraftGenerator,
    MorningPlanPlanner,
)
from app.runtime import StateStore
from app.usecases.lifecycle import wake_up
from app.domain.models import FocusMode, WakeMode
from app.world.models import WorldState
from app.world.repository import FileWorldRepository, WorldRepository
from app.world.service import WorldStateService


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_runtime_initialized(app)

    try:
        yield
    finally:
        stop_event = app.state.stop_event
        worker = app.state.autonomy_thread
        if worker.is_alive():
            stop_event.set()
            worker.join(timeout=1.0)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    memory_repository = FileMemoryRepository(get_memory_storage_path())
    state_store = StateStore(
        memory_repository=memory_repository,
        storage_path=get_state_storage_path(),
    )
    goal_repository = FileGoalRepository(get_goal_storage_path())
    world_repository = FileWorldRepository(get_world_storage_path())
    stop_event = Event()
    loop = AutonomyLoop(state_store, memory_repository, goal_repository)
    world_state_service = WorldStateService()

    build_world_state(
        state_store,
        goal_repository,
        memory_repository,
        world_repository,
        world_state_service,
    )

    def run_loop() -> None:
        while not stop_event.wait(5.0):
            loop.tick_once()

    worker = Thread(target=run_loop, name="autonomy-loop", daemon=True)
    worker.start()

    target_app.state.state_store = state_store
    target_app.state.memory_repository = memory_repository
    target_app.state.goal_repository = goal_repository
    target_app.state.world_repository = world_repository
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    gateway = ChatGateway.from_env()
    try:
        yield gateway
    finally:
        gateway.close()


def get_memory_repository() -> MemoryRepository:
    _ensure_runtime_initialized(app)
    return app.state.memory_repository


def get_state_store() -> StateStore:
    _ensure_runtime_initialized(app)
    return app.state.state_store


def get_goal_repository() -> GoalRepository:
    _ensure_runtime_initialized(app)
    return app.state.goal_repository


def get_world_repository() -> WorldRepository:
    _ensure_runtime_initialized(app)
    return app.state.world_repository


def get_world_state_service() -> WorldStateService:
    return WorldStateService()


def get_morning_plan_planner() -> MorningPlanPlanner:
    return MorningPlanPlanner()


def get_morning_plan_draft_generator() -> Generator[MorningPlanDraftGenerator | None, None, None]:
    if not is_morning_plan_llm_enabled():
        yield None
        return

    try:
        gateway = ChatGateway.from_env()
    except RuntimeError:
        yield None
        return

    try:
        yield LLMMorningPlanDraftGenerator(gateway)
    finally:
        gateway.close()


def build_chat_messages(
    memory_repository: MemoryRepository,
    state_store: StateStore,
    goal_repository: GoalRepository,
    user_message: str,
    limit: int = 6,
) -> list[ChatMessage]:
    relevant_events = memory_repository.search_relevant(user_message, limit=limit)
    state = state_store.get()
    focus_goal = (
        None
        if not state.active_goal_ids
        else goal_repository.get_goal(state.active_goal_ids[0])
    )
    focus_messages = (
        []
        if focus_goal is None
        else [ChatMessage(role="system", content=f"你当前最在意的焦点目标：{focus_goal.title}。")]
    )
    latest_plan_completion = _find_latest_today_plan_completion(memory_repository)
    completion_messages = (
        []
        if latest_plan_completion is None
        else [ChatMessage(role="system", content=f"你今天刚完成的一件事：{latest_plan_completion}")]
    )
    world_messages = [
        ChatMessage(role="system", content=f"最近你的世界事件：{event.content}")
        for event in relevant_events
        if event.kind == "world"
    ]
    inner_messages = [
        ChatMessage(role="system", content=f"最近你的内在阶段记忆：{event.content}")
        for event in relevant_events
        if event.kind == "inner"
    ]
    autobio_messages = [
        ChatMessage(role="system", content=f"最近你的自传式回顾：{event.content}")
        for event in relevant_events
        if event.kind == "autobio"
    ]
    messages = [
        ChatMessage(role=event.role, content=event.content)
        for event in relevant_events
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    messages.append(ChatMessage(role="user", content=user_message))
    return [
        *focus_messages,
        *completion_messages,
        *world_messages,
        *inner_messages,
        *autobio_messages,
        *messages,
    ]


def build_world_state(
    state_store: StateStore,
    goal_repository: GoalRepository,
    memory_repository: MemoryRepository,
    world_repository: WorldRepository,
    world_state_service: WorldStateService,
) -> WorldState:
    state = state_store.get()
    focused_goals = [
        goal
        for goal_id in state.active_goal_ids
        if (goal := goal_repository.get_goal(goal_id)) is not None
    ]
    latest_world_event = next(
        (
            event
            for event in memory_repository.list_recent(limit=20)
            if event.kind == "world"
        ),
        None,
    )
    world_state = world_state_service.bootstrap(
        being_state=state,
        focused_goals=focused_goals,
        latest_event=None if latest_world_event is None else latest_world_event.content,
        latest_event_at=None if latest_world_event is None else latest_world_event.created_at,
    )
    return world_repository.save_world_state(world_state)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
def get_state(
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    return state_store.get().model_dump()


@app.get("/messages")
def get_messages(
    memory_repository: MemoryRepository = Depends(get_memory_repository),
) -> ChatHistoryResponse:
    recent_events = list(reversed(memory_repository.list_recent(limit=20)))
    messages = [
        ChatHistoryMessage(role=event.role, content=event.content)
        for event in recent_events
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    return ChatHistoryResponse(messages=messages)


@app.get("/autobio")
def get_autobio(
    memory_repository: MemoryRepository = Depends(get_memory_repository),
) -> dict[str, list[str]]:
    recent_events = list(reversed(memory_repository.list_recent(limit=20)))
    entries = [
        event.content
        for event in recent_events
        if event.kind == "autobio"
    ]
    return {"entries": _deduplicate_entries(entries)}


@app.get("/goals")
def get_goals(
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> dict[str, list[Goal]]:
    return {"goals": goal_repository.list_goals()}


def _deduplicate_entries(entries: list[str]) -> list[str]:
    unique_entries: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        unique_entries.append(entry)

    return unique_entries


def _find_recent_autobio(memory_repository: MemoryRepository) -> str | None:
    recent_events = memory_repository.list_recent(limit=20)
    return next((event.content for event in recent_events if event.kind == "autobio"), None)


def _find_latest_today_plan_completion(memory_repository: MemoryRepository) -> str | None:
    recent_events = memory_repository.list_recent(limit=20)
    return next(
        (
            event.content
            for event in recent_events
            if event.kind == "autobio" and "今天的计划" in event.content
        ),
        None,
    )


def _summarize_latest_self_improvement(state) -> str | None:
    job = state.self_improvement_job
    if job is None:
        return None
    if job.status.value == "applied":
        return f"我补强了 {job.target_area}，并通过了验证。"
    if job.status.value == "failed":
        return f"我尝试补强 {job.target_area}，但还没通过验证。"
    return None


def _select_wake_goal(
    goal_repository: GoalRepository,
    recent_autobio: str | None,
) -> Goal | None:
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


@app.get("/world")
def get_world(
    state_store: StateStore = Depends(get_state_store),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    world_repository: WorldRepository = Depends(get_world_repository),
    world_state_service: WorldStateService = Depends(get_world_state_service),
) -> WorldState:
    return build_world_state(
        state_store,
        goal_repository,
        memory_repository,
        world_repository,
        world_state_service,
    )


@app.post("/goals/{goal_id}/status")
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
                            "focus_mode": (
                                FocusMode.AUTONOMY if state.mode == WakeMode.AWAKE else FocusMode.SLEEPING
                            ),
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


@app.post("/lifecycle/wake")
def wake(
    state_store: StateStore = Depends(get_state_store),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    planner: MorningPlanPlanner = Depends(get_morning_plan_planner),
    draft_generator: MorningPlanDraftGenerator | None = Depends(get_morning_plan_draft_generator),
) -> dict:
    current_state = state_store.get()
    recent_autobio = _find_recent_autobio(memory_repository)
    selected_goal = _select_wake_goal(goal_repository, recent_autobio)
    waking_state = wake_up(recent_autobio=recent_autobio).model_copy(
        update={"self_improvement_job": current_state.self_improvement_job}
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


@app.post("/lifecycle/sleep")
def sleep(
    state_store: StateStore = Depends(get_state_store),
) -> dict:
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


@app.post("/chat")
def chat(
    request: ChatRequest,
    gateway: ChatGateway = Depends(get_chat_gateway),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    state_store: StateStore = Depends(get_state_store),
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> ChatResult:
    state = state_store.get()
    focus_goal = (
        None
        if not state.active_goal_ids
        else goal_repository.get_goal(state.active_goal_ids[0])
    )
    latest_plan_completion = _find_latest_today_plan_completion(memory_repository)
    latest_self_improvement = _summarize_latest_self_improvement(state)
    result = gateway.create_response(
        build_chat_messages(memory_repository, state_store, goal_repository, request.message),
        instructions=build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_improvement=latest_self_improvement,
            user_message=request.message,
        ),
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content=request.message,
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            role="assistant",
            content=result.output_text,
        )
    )
    return result
