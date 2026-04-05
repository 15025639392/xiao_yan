from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from logging import getLogger
from uuid import uuid4

logger = getLogger(__name__)
from threading import Event, Thread

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import ClassVar

from app.config import (
    get_goal_storage_path,
    get_memory_storage_path,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
    is_morning_plan_llm_enabled,
    get_chat_context_limit,
)
from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, FocusMode, SelfProgrammingStatus, WakeMode
from app.goals.models import Goal, GoalStatus, GoalStatusUpdate
from app.goals.repository import FileGoalRepository, GoalRepository
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResumeRequest,
    ChatResult,
    ChatSubmissionResult,
)
from app.memory.models import MemoryEntry, MemoryKind, MemoryEmotion, MemoryStrength
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.realtime import AppRealtimeHub
from app.memory.service import MemoryService
from app.persona.models import (
    FormalLevel,
    ExpressionHabit,
    SentenceStyle,
    PersonaProfile,
)
from app.persona.expression_mapper import ExpressionStyleMapper
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import FilePersonaRepository, PersonaService
from app.persona.templates import PersonaTemplateManager, PERSONA_TYPES
from app.persona.validator import PersonaValidator
from app.planning.morning_plan import (
    LLMMorningPlanDraftGenerator,
    MorningPlanDraftGenerator,
    MorningPlanPlanner,
)
from app.runtime import StateStore
from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox, ToolSafetyLevel
from app.usecases.lifecycle import wake_up
from app.world.models import WorldState
from app.world.repository import FileWorldRepository, WorldRepository
from app.world.service import WorldStateService
from typing import Any


# ═══════════════════════════════════════════════════
# 运行时配置管理
# ═══════════════════════════════════════════════════

class RuntimeConfig:
    """运行时配置（可在运行时更新）"""

    _instance: ClassVar["RuntimeConfig"] | None = None

    def __new__(cls) -> "RuntimeConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._chat_context_limit = get_chat_context_limit()
        return cls._instance

    @property
    def chat_context_limit(self) -> int:
        return self._chat_context_limit

    @chat_context_limit.setter
    def chat_context_limit(self, value: int) -> None:
        self._chat_context_limit = max(1, min(20, value))


def get_runtime_config() -> RuntimeConfig:
    """获取运行时配置实例"""
    return RuntimeConfig()


# ═══════════════════════════════════════════════════
# FastAPI 应用和生命周期
# ═══════════════════════════════════════════════════


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
    persona_repository = FilePersonaRepository(get_persona_storage_path())
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
    stop_event = Event()

    # 尝试创建 Gateway（用于 LLM 自我编程），失败则不注入
    try:
        loop_gateway = ChatGateway.from_env()
    except RuntimeError:
        loop_gateway = None

    loop = AutonomyLoop(
        state_store,
        memory_repository,
        goal_repository,
        gateway=loop_gateway,
    )
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
    target_app.state.persona_service = persona_service
    target_app.state.memory_service = memory_service
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker


def _compose_world_state(
    state_store: StateStore,
    goal_repository: GoalRepository,
    memory_repository: MemoryRepository,
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
    return world_state_service.bootstrap(
        being_state=state,
        focused_goals=focused_goals,
        latest_event=None if latest_world_event is None else latest_world_event.content,
        latest_event_at=None if latest_world_event is None else latest_world_event.created_at,
    )


def _build_runtime_payload(target_app: FastAPI) -> dict:
    state_store = target_app.state.state_store
    memory_repository = target_app.state.memory_repository
    goal_repository = target_app.state.goal_repository

    messages = [
        ChatHistoryMessage(role=event.role, content=event.content).model_dump()
        for event in reversed(memory_repository.list_recent(limit=20))
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    autobio_entries = [
        event.content
        for event in reversed(memory_repository.list_recent(limit=20))
        if event.kind == "autobio"
    ]
    world_state = _compose_world_state(
        state_store,
        goal_repository,
        memory_repository,
        WorldStateService(),
    )

    return {
        "state": state_store.get().model_dump(mode="json"),
        "messages": messages,
        "goals": [goal.model_dump(mode="json") for goal in goal_repository.list_goals()],
        "world": world_state.model_dump(mode="json"),
        "autobio": _deduplicate_entries(autobio_entries),
    }


def _build_memory_payload(target_app: FastAPI) -> dict:
    memory_service = target_app.state.memory_service
    return {
        "summary": memory_service.get_memory_summary(),
        "timeline": memory_service.get_memory_timeline(limit=40),
    }


def _build_persona_payload(target_app: FastAPI) -> dict:
    persona_service = target_app.state.persona_service
    return {
        "profile": persona_service.get_profile().model_dump(mode="json"),
        "emotion": persona_service.get_emotion_summary(),
    }


def _build_app_snapshot(target_app: FastAPI) -> dict:
    return {
        "runtime": _build_runtime_payload(target_app),
        "memory": _build_memory_payload(target_app),
        "persona": _build_persona_payload(target_app),
    }


def _ensure_realtime_hub_initialized(target_app: FastAPI) -> None:
    existing_hub = getattr(target_app.state, "realtime_hub", None)
    if existing_hub is not None and not existing_hub.loop.is_closed():
        return

    loop = asyncio.get_running_loop()
    hub = AppRealtimeHub(loop=loop, snapshot_builder=lambda: _build_app_snapshot(target_app))
    target_app.state.realtime_hub = hub

    state_store = target_app.state.state_store
    memory_repository = target_app.state.memory_repository
    goal_repository = target_app.state.goal_repository
    persona_service = target_app.state.persona_service

    if hasattr(state_store, "set_on_change_callback"):
        state_store.set_on_change_callback(hub.publish_runtime)
    if hasattr(memory_repository, "set_on_change_callback"):
        memory_repository.set_on_change_callback(lambda: (hub.publish_runtime(), hub.publish_memory()))
    if hasattr(goal_repository, "set_on_change_callback"):
        goal_repository.set_on_change_callback(hub.publish_runtime)
    if hasattr(persona_service, "set_on_change_callback"):
        persona_service.set_on_change_callback(hub.publish_persona)


def get_persona_service() -> PersonaService:
    _ensure_runtime_initialized(app)
    return app.state.persona_service  # type: ignore[attr-defined]


def get_memory_service() -> MemoryService:
    _ensure_runtime_initialized(app)
    return app.state.memory_service  # type: ignore[attr-defined]


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
    limit: int | None = None,
) -> list[ChatMessage]:
    # 使用运行时配置，如果未指定则使用默认值
    if limit is None:
        config = get_runtime_config()
        limit = config.chat_context_limit
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
    world_state = _compose_world_state(
        state_store,
        goal_repository,
        memory_repository,
        world_state_service,
    )
    return world_repository.save_world_state(world_state)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/app")
async def app_realtime(websocket: WebSocket) -> None:
    _ensure_runtime_initialized(app)
    _ensure_realtime_hub_initialized(app)
    hub = app.state.realtime_hub
    await hub.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)


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


def _summarize_latest_self_programming(state) -> str | None:
    job = state.self_programming_job
    if job is None:
        return None
    if job.status.value == "applied":
        return f"我补强了 {job.target_area}，并通过了验证。"
    if job.status.value == "failed":
        return f"我尝试补强 {job.target_area}，但还没通过验证。"
    return None


def _merge_chat_stream_content(current_content: str, delta: str) -> str:
    if not current_content:
        return delta

    if not delta:
        return current_content

    if delta.startswith(current_content):
        return delta

    if current_content.startswith(delta) or delta in current_content:
        return current_content

    max_overlap = min(len(current_content), len(delta))
    for overlap in range(max_overlap, 0, -1):
        if current_content[-overlap:] == delta[:overlap]:
            return f"{current_content}{delta[overlap:]}"

    return f"{current_content}{delta}"


def _build_resume_instruction(partial_content: str) -> str:
    return (
        "这是一次失败后的继续生成。"
        "你必须紧接着下面这段 assistant 已输出内容继续生成，"
        "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
        f"已输出内容：\n{partial_content}"
    )


def _run_chat_submission(
    *,
    gateway: ChatGateway,
    chat_messages: list[ChatMessage],
    instructions: str,
    assistant_message_id: str,
    initial_output_text: str = "",
) -> tuple[ChatSubmissionResult, str]:
    response_id: str | None = None
    output_text = initial_output_text
    started = False
    hub = getattr(app.state, "realtime_hub", None)

    try:
        for event in gateway.stream_response(chat_messages, instructions=instructions):
            event_type = event["type"]
            if event_type == "response_started":
                response_id = event.get("response_id") or response_id
                if hub is not None and not started:
                    hub.publish_chat_started(assistant_message_id, response_id=response_id)
                    started = True
                continue

            if event_type == "text_delta":
                if hub is not None and not started:
                    hub.publish_chat_started(assistant_message_id, response_id=response_id)
                    started = True

                delta = event.get("delta") or ""
                if not delta:
                    continue

                output_text = _merge_chat_stream_content(output_text, delta)
                if hub is not None:
                    hub.publish_chat_delta(assistant_message_id, delta)
                continue

            if event_type == "response_completed":
                response_id = event.get("response_id") or response_id
                output_text = _merge_chat_stream_content(
                    output_text,
                    event.get("output_text") or "",
                )
                continue

            if event_type == "response_failed":
                error_message = event.get("error") or "streaming failed"
                if hub is not None:
                    hub.publish_chat_failed(assistant_message_id, error_message)
                raise HTTPException(status_code=502, detail=error_message)
    except HTTPException:
        raise
    except Exception as exception:
        if hub is not None:
            hub.publish_chat_failed(assistant_message_id, str(exception))
        raise HTTPException(status_code=502, detail=str(exception)) from exception

    if hub is not None and not started:
        hub.publish_chat_started(assistant_message_id, response_id=response_id)
    if hub is not None:
        hub.publish_chat_completed(assistant_message_id, response_id, output_text)

    return (
        ChatSubmissionResult(
            response_id=response_id,
            assistant_message_id=assistant_message_id,
        ),
        output_text,
    )


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
    persona_service: PersonaService = Depends(get_persona_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatSubmissionResult:
    state = state_store.get()
    focus_goal = (
        None
        if not state.active_goal_ids
        else goal_repository.get_goal(state.active_goal_ids[0])
    )
    latest_plan_completion = _find_latest_today_plan_completion(memory_repository)
    latest_self_programming = _summarize_latest_self_programming(state)

    # 注入人格 system prompt + 情绪推断
    persona_system_prompt = persona_service.build_system_prompt()
    persona_service.infer_chat_emotion(request.message)

    # 注入记忆上下文到 prompt
    memory_context = memory_service.build_memory_prompt_context(
        user_message=request.message,
        max_chars=600,
    )

    # 计算情绪驱动的表达风格覆盖
    current_emotion = persona_service.profile.emotion
    style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
    style_override = style_mapper.map_from_state(current_emotion)
    expression_style_context = style_mapper.build_style_prompt(style_override)

    chat_messages = build_chat_messages(memory_repository, state_store, goal_repository, request.message)
    instructions = build_chat_instructions(
        focus_goal_title=None if focus_goal is None else focus_goal.title,
        latest_plan_completion=latest_plan_completion,
        latest_self_programming=latest_self_programming,
        user_message=request.message,
        persona_system_prompt=persona_system_prompt,
        memory_context=memory_context or None,
        expression_style_context=expression_style_context or None,
    )

    assistant_message_id = f"assistant_{uuid4().hex}"
    submission, output_text = _run_chat_submission(
        gateway=gateway,
        chat_messages=chat_messages,
        instructions=instructions,
        assistant_message_id=assistant_message_id,
    )

    # 从对话中提取记忆并统一保存，避免原始对话与提取结果重复落库
    extracted = memory_service.extract_from_conversation(
        user_message=request.message,
        assistant_response=output_text,
    )
    for entry in extracted:
        memory_service.save(entry)

    return submission


@app.post("/chat/resume")
def resume_chat(
    request: ChatResumeRequest,
    gateway: ChatGateway = Depends(get_chat_gateway),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    state_store: StateStore = Depends(get_state_store),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    persona_service: PersonaService = Depends(get_persona_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatSubmissionResult:
    state = state_store.get()
    focus_goal = (
        None
        if not state.active_goal_ids
        else goal_repository.get_goal(state.active_goal_ids[0])
    )
    latest_plan_completion = _find_latest_today_plan_completion(memory_repository)
    latest_self_programming = _summarize_latest_self_programming(state)

    persona_system_prompt = persona_service.build_system_prompt()
    persona_service.infer_chat_emotion(request.message)
    memory_context = memory_service.build_memory_prompt_context(
        user_message=request.message,
        max_chars=600,
    )
    current_emotion = persona_service.profile.emotion
    style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
    style_override = style_mapper.map_from_state(current_emotion)
    expression_style_context = style_mapper.build_style_prompt(style_override)

    chat_messages = build_chat_messages(memory_repository, state_store, goal_repository, request.message)
    instructions = build_chat_instructions(
        focus_goal_title=None if focus_goal is None else focus_goal.title,
        latest_plan_completion=latest_plan_completion,
        latest_self_programming=latest_self_programming,
        user_message=request.message,
        persona_system_prompt=persona_system_prompt,
        memory_context=memory_context or None,
        expression_style_context=expression_style_context or None,
    )
    instructions = f"{instructions}\n\n{_build_resume_instruction(request.partial_content)}"

    submission, output_text = _run_chat_submission(
        gateway=gateway,
        chat_messages=chat_messages,
        instructions=instructions,
        assistant_message_id=request.assistant_message_id,
        initial_output_text=request.partial_content,
    )

    extracted = memory_service.extract_from_conversation(
        user_message=request.message,
        assistant_response=output_text,
    )
    for entry in extracted:
        memory_service.save(entry)

    return submission


# ═══════════════════════════════════════════════════
# 审批交互 API
# ═══════════════════════════════════════════════════

class ApprovalRequest(BaseModel):
    """审批请求体（approve/reject 共用）"""
    reason: str | None = None  # 可选：拒绝原因或审批备注


class ConfigUpdateRequest(BaseModel):
    """配置更新请求体"""
    chat_context_limit: int = Field(..., ge=1, le=20, description="聊天上下文相关事件数量限制（1-20）")


class ConfigResponse(BaseModel):
    """配置响应"""
    chat_context_limit: int


@app.post("/self-programming/{job_id}/approve")
def approve_job(
    job_id: str,
    request: ApprovalRequest | None = None,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """批准自我编程 Job — 将状态从 pending_approval 推进到 verifying"""
    from app.self_programming.service import SelfProgrammingService

    state = state_store.get()
    job = state.self_programming_job
    if job is None or job.id != job_id:
        raise HTTPException(status_code=404, detail="Job not found or not current")
    if job.status != SelfProgrammingStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

    # 推进到 VERIFYING 阶段（后续 tick_job 会接手验证流程）
    approved_job = job.model_copy(
        update={
            "status": SelfProgrammingStatus.VERIFYING,
            "current_thought_override": "用户已批准，开始执行验证...",
        }
    )
    # 更新状态
    new_state = state.model_copy(
        update={
            "self_programming_job": approved_job,
            "current_thought": f"太好了，我的自我编程方案得到了批准，正在对 {job.target_area} 执行验证。",
        }
    )
    state_store.set(new_state)
    return {"success": True, "message": "已批准", "job_id": job_id}


@app.post("/self-programming/{job_id}/reject")
def reject_job(
    job_id: str,
    request: ApprovalRequest,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """拒绝自我编程 Job — 标记为 rejected 并回滚（如果已 apply）"""
    from app.self_programming.executor import SelfProgrammingExecutor

    state = state_store.get()
    job = state.self_programming_job
    if job is None or job.id != job_id:
        raise HTTPException(status_code=404, detail="Job not found or not current")
    if job.status != SelfProgrammingStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

    rejected_job = job.model_copy(
        update={
            "status": SelfProgrammingStatus.REJECTED,
            "approval_reason": request.reason or "用户拒绝",
            "rollback_info": f"被用户拒绝: {request.reason or '无原因'}",
        }
    )
    new_state = _finish_state_with_rejection(state, rejected_job)
    state_store.set(new_state)
    return {"success": True, "message": "已拒绝", "job_id": job_id}


def _finish_state_with_rejection(state: BeingState, job) -> BeingState:
    """拒绝后的终态（类似 _finish_state 但标记为拒绝）"""
    return state.model_copy(
        update={
            "focus_mode": FocusMode.AUTONOMY,
            "self_programming_job": job,
            "current_thought": (
                f"这次关于 {job.target_area} 的自我编程被拒绝了。"
                f"原因：{job.approval_reason or '未知'}。"
                "我会记住这次的教训，下次做得更好。"
            ),
        }
    )


# ═══════════════════════════════════════════════════
# 自我编程历史 / 回滚 / 健康度 API（前端已对接）
# ═══════════════════════════════════════════════════

def _get_history() -> Any:
    """懒加载获取 SelfProgrammingHistory 实例。"""
    from app.self_programming.history_store import SelfProgrammingHistory

    if not hasattr(_get_history, "_instance"):
        _get_history._instance = SelfProgrammingHistory(in_memory=True)
    return _get_history._instance


@app.get("/self-programming/history")
def get_self_programming_history(
    limit: int = 50,
) -> dict:
    """获取自我编程历史记录列表。"""
    history = _get_history()
    entries = history.get_recent(limit)
    return {
        "entries": [
            {
                "job_id": e.job_id,
                "target_area": e.target_area,
                "reason": e.reason,
                "status": e.status.value if hasattr(e.status, 'value') else str(e.status),
                "outcome": e.patch_summary or e.spec[:80],
                "touched_files": list(e.touched_files),
                "created_at": e.created_at,
                "completed_at": e.completed_at or None,
                "health_score": None,   # 历史条目暂不存健康度
                "had_rollback": (e.status.value if hasattr(e.status, 'value') else str(e.status)) == "rolled_back",
            }
            for e in entries
        ],
    }


@app.post("/self-programming/{job_id}/rollback")
def rollback_job_endpoint(
    job_id: str,
    request: ApprovalRequest | None = None,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """回滚指定自我编程 Job。"""
    from app.self_programming.executor import SelfProgrammingExecutor

    state = state_store.get()
    job = state.self_programming_job

    # 允许对当前活跃 job 或指定 job 执行回滚
    if job is not None and job.id == job_id:
        target_job = job
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in current state")

    try:
        executor = SelfProgrammingExecutor()
        result = executor.rollback(target_job, reason=request.reason if request else None)

        rollback_info = getattr(result, 'rollback_info', '') or ''
        new_state = state.model_copy(
            update={
                "self_programming_job": result,
                "current_thought": f"自我编程 {job_id} 已回滚: {rollback_info[:100]}",
            }
        )
        state_store.set(new_state)
        return {"success": True, "message": rollback_info or "回滚成功"}
    except Exception as exc:
        logger.exception("Rollback failed")
        raise HTTPException(status_code=500, detail=f"回滚失败: {exc}")


# ═══════════════════════════════════════════════════
# 配置 API
# ═══════════════════════════════════════════════════


@app.get("/config")
def get_config() -> ConfigResponse:
    """获取当前配置"""
    config = get_runtime_config()
    return ConfigResponse(chat_context_limit=config.chat_context_limit)


@app.put("/config")
def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """更新配置"""
    config = get_runtime_config()
    config.chat_context_limit = request.chat_context_limit
    return ConfigResponse(chat_context_limit=config.chat_context_limit)


# ═══════════════════════════════════════════════════
# 人格 API
# ═══════════════════════════════════════════════════


class PersonaUpdateRequest(BaseModel):
    """人格更新请求体"""
    name: str | None = None
    identity: str | None = None
    origin_story: str | None = None


class PersonalityUpdateRequest(BaseModel):
    """性格维度更新请求体"""
    openness: int | None = None
    conscientiousness: int | None = None
    extraversion: int | None = None
    agreeableness: int | None = None
    neuroticism: int | None = None


class SpeakingStyleUpdateRequest(BaseModel):
    """说话风格更新请求体"""
    formal_level: FormalLevel | None = None
    sentence_style: SentenceStyle | None = None
    expression_habit: ExpressionHabit | None = None
    emoji_usage: str | None = None
    verbal_tics: list[str] | None = None
    response_length: str | None = None


class PersonaCreateFromTemplateRequest(BaseModel):
    """从模板创建人格请求体"""
    template_type: PERSONA_TYPES = Field(..., description="选择的人格模板类型")
    customizations: dict | None = Field(None, description="自定义配置")


# ============ 人格模板API ============

@app.get("/persona/templates")
async def list_persona_templates():
    """获取所有可用的人格模板"""
    manager = PersonaTemplateManager()
    templates = manager.list_templates()
    
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "personality": t.personality.model_dump(),
                "speaking_style": t.speaking_style.model_dump(),
            }
            for t in templates
        ]
    }


@app.post("/persona/from-template")
async def create_persona_from_template(request: PersonaCreateFromTemplateRequest):
    """从模板创建人格"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template(
        request.template_type,
        request.customizations
    )
    
    # 验证创建的人格
    validator = PersonaValidator()
    report = validator.get_validation_report(persona)
    
    return {
        "persona": persona.model_dump(),
        "validation": report
    }


@app.post("/persona/validate")
async def validate_persona(persona: PersonaProfile):
    """验证人格配置"""
    validator = PersonaValidator()
    report = validator.get_validation_report(persona)
    return report


@app.get("/persona")
def get_persona(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取完整人格档案"""
    profile = persona_service.get_profile()
    return profile.model_dump()


@app.put("/persona")
def update_persona(
    request: PersonaUpdateRequest,
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """更新人格基础信息"""
    updated = persona_service.update_profile(
        name=request.name,
        identity=request.identity,
        origin_story=request.origin_story,
    )
    return {"success": True, "profile": updated.model_dump()}


@app.put("/persona/personality")
def update_personality(
    request: PersonalityUpdateRequest,
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """更新性格维度"""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个性格维度")
    updated = persona_service.update_personality(**updates)
    return {"success": True, "profile": updated.model_dump()}


@app.put("/persona/speaking-style")
def update_speaking_style(
    request: SpeakingStyleUpdateRequest,
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """更新说话风格"""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个风格字段")
    updated = persona_service.update_speaking_style(**updates)
    return {"success": True, "profile": updated.model_dump()}


@app.post("/persona/reset")
def reset_persona(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """重置为默认人格"""
    profile = persona_service.reset_to_default()
    return {"success": True, "profile": profile.model_dump()}


@app.post("/persona/initialize")
def initialize_persona(
    state_store: StateStore = Depends(get_state_store),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """初始化数字人：清空所有数据并重置为初始状态"""
    from app.domain.models import BeingState, FocusMode, WakeMode

    # 清空所有记忆
    memory_count = memory_repository.clear_all()

    # 清空所有目标
    goal_count = goal_repository.clear_all()

    # 重置人格为默认值
    profile = persona_service.reset_to_default()

    # 重置状态为初始状态
    initial_state = BeingState(
        mode=WakeMode.SLEEPING,
        focus_mode=FocusMode.SLEEPING,
        current_thought=None,
        active_goal_ids=[],
        today_plan=None,
        last_action=None,
        self_programming_job=None,
    )
    state_store.set(initial_state)

    return {
        "success": True,
        "message": "数字人已初始化",
        "cleared": {
            "memories": memory_count,
            "goals": goal_count,
        },
        "profile": profile.model_dump(),
    }


# ── 情绪 API ──────────────────────────────────────────


@app.get("/persona/emotion")
def get_emotion_state(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取当前情绪状态详情"""
    return persona_service.get_emotion_summary()



# ═══════════════════════════════════════════════════
# 记忆与人格联动 API
# ═══════════════════════════════════════════════════


class MemoryCreateRequest(BaseModel):
    """创建记忆请求体"""
    kind: MemoryKind
    content: str
    role: str | None = None
    strength: MemoryStrength = MemoryStrength.NORMAL
    importance: int = 5
    emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL
    keywords: list[str] | None = None
    subject: str | None = None


@app.get("/memory/summary")
def get_memory_summary(
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """获取记忆系统统计摘要"""
    return memory_service.get_memory_summary()


@app.get("/memory/timeline")
def get_memory_timeline(
    limit: int = 30,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """获取记忆时间线（前端展示用）"""
    return {"entries": memory_service.get_memory_timeline(limit=limit)}


@app.get("/memory/search")
def search_memories(
    q: str,
    limit: int = 10,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """搜索相关记忆"""
    result = memory_service.search(q, limit=limit)
    return {
        "entries": [e.to_display_dict() for e in result.entries],
        "total_count": result.total_count,
        "query_summary": result.query_summary,
    }


@app.post("/memory")
def create_memory(
    request: MemoryCreateRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """手动创建一条记忆"""
    entry = memory_service.create(
        kind=request.kind,
        content=request.content,
        role=request.role,
        strength=request.strength,
        importance=request.importance,
        emotion_tag=request.emotion_tag,
        keywords=request.keywords,
        subject=request.subject,
        source_context="手动创建",
    )
    return {"success": True, "entry": entry.to_display_dict()}


# ── 记忆操作 API（删除 / 更新 / 标星）──

class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    kind: MemoryKind | None = None
    importance: int | None = Field(default=None, ge=0, le=10)
    strength: MemoryStrength | None = None
    emotion_tag: MemoryEmotion | None = None
    keywords: list[str] | None = None
    subject: str | None = None


@app.delete("/memory/{memory_id}")
def delete_memory(
    memory_id: str,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """删除指定 ID 的记忆"""
    success = memory_service.delete(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
    return {"success": True, "deleted_id": memory_id}


class MemoryBatchDeleteRequest(BaseModel):
    memory_ids: list[str]


@app.post("/memory/batch-delete")
def batch_delete_memories(
    request: MemoryBatchDeleteRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """批量删除多条记忆"""
    if not request.memory_ids:
        return {"success": True, "deleted": 0, "failed": 0}

    result = memory_service.delete_many(request.memory_ids)
    return {
        "success": result["failed"] == 0,
        "deleted": result["deleted"],
        "failed": result["failed"],
        "total": len(request.memory_ids),
    }


@app.put("/memory/{memory_id}")
def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """更新记忆内容或属性"""
    success = memory_service.update(
        memory_id,
        content=request.content,
        kind=request.kind,
        importance=request.importance,
        strength=request.strength,
        emotion_tag=request.emotion_tag,
        keywords=request.keywords,
        subject=request.subject,
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    # 返回更新后的条目
    entry = memory_service.get_by_id(memory_id)
    return {
        "success": True,
        "entry": entry.to_display_dict() if entry else None,
    }


@app.post("/memory/{memory_id}/star")
def star_memory(
    memory_id: str,
    important: bool = True,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """标记/取消标记记忆为重要"""
    success = memory_service.star(memory_id, important=important)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
    return {"success": True, "starred": important, "memory_id": memory_id}


# ═══════════════════════════════════════════════════
# 工具执行 API
# ═══════════════════════════════════════════════════

# ── 依赖注入 ────────────────────────────────────────

_tool_runner_instance: CommandRunner | None = None
_file_tools_instance: Any = None


def _get_command_runner() -> CommandRunner:
    global _tool_runner_instance
    if _tool_runner_instance is None:
        from pathlib import Path as _P
        _workspace = _P(__file__).resolve().parents[4]
        _sandbox = CommandSandbox.with_defaults(
            max_level=ToolSafetyLevel.RESTRICTED,
            allowed_base_path=_workspace,
        )
        _tool_runner_instance = CommandRunner(
            _sandbox,
            working_directory=_workspace,
            timeout_seconds=60.0,
        )
    return _tool_runner_instance


def _get_file_tools():
    global _file_tools_instance
    if _file_tools_instance is None:
        from pathlib import Path as _P
        from app.tools.file_tools import FileTools
        _workspace = _P(__file__).resolve().parents[4]
        _file_tools_instance = FileTools(allowed_base_path=_workspace)
    return _file_tools_instance


# ── 数据模型 ──────────────────────────────────────────


class ToolExecuteRequest(BaseModel):
    """命令执行请求体"""
    command: str
    timeout_override: float | None = None  # 可选覆盖超时


class FileReadRequest(BaseModel):
    """文件读取请求体"""
    path: str
    max_bytes: int = 512 * 1024  # 512KB default


class FileSearchRequest(BaseModel):
    """文件内容搜索请求体"""
    query: str
    search_path: str = "."
    file_pattern: str = "*.py"
    max_results: int = 20


class DirectoryListRequest(BaseModel):
    """目录列表请求体"""
    path: str = "."
    recursive: bool = False
    pattern: str | None = None


# ── API 端点 ──────────────────────────────────────────


@app.get("/tools")
def list_tools() -> dict:
    """列出当前可用工具及其元数据。"""
    runner = _get_command_runner()
    tools = runner.sandbox.list_available_tools()

    # 按类别分组
    by_category: dict[str, list] = {}
    for t in tools:
        cat = t.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append({
            "name": t.name,
            "description": t.description,
            "safety_level": t.safety_level.value,
            "examples": t.examples[:3],
        })

    return {
        "total_count": len(tools),
        "by_category": by_category,
        "safety_levels": [sl.value for sl in ToolSafetyLevel],
    }


@app.post("/tools/execute")
def execute_tool(
    request: ToolExecuteRequest,
) -> dict:
    """执行一个工具命令。

    返回增强的执行结果（含 exit_code / stderr / duration）。
    """
    runner = _get_command_runner()
    
    # 支持临时超时覆盖
    original_timeout = runner.timeout_seconds
    if request.timeout_override and request.timeout_override > 0:
        runner.timeout_seconds = min(request.timeout_override, 120.0)

    result = runner.run(request.command)

    # 恢复原始超时
    runner.timeout_seconds = original_timeout

    return {
        **result.to_dict(),
    }


@app.get("/tools/history")
def get_tool_history(limit: int = 30) -> dict:
    """获取最近执行的工具命令历史。"""
    runner = _get_command_runner()
    return {
        "entries": runner.get_history(limit),
        "total": len(runner._history),
    }


@app.delete("/tools/history")
def clear_tool_history() -> dict:
    """清空执行历史。"""
    runner = _get_command_runner()
    count = runner.clear_history()
    return {"cleared": count, "message": f"已清除 {count} 条历史记录"}


# ── 文件操作 API ────────────────────────────────────


@app.get("/tools/files/read")
def api_read_file(path: str, max_bytes: int = 512 * 1024) -> dict:
    """读取文件内容。"""
    ft = _get_file_tools()
    result = ft.read_file(path, max_bytes=max_bytes)
    return result.to_dict()


@app.get("/tools/files/list")
def api_list_directory(
    path: str = ".",
    recursive: bool = False,
    pattern: str | None = None,
) -> dict:
    """列出目录内容。"""
    ft = _get_file_tools()
    result = ft.list_directory(path, recursive=recursive, pattern=pattern)
    return result.to_dict()


@app.get("/tools/files/search")
def api_search_files(
    query: str,
    search_path: str = ".",
    file_pattern: str = "*.py",
    max_results: int = 20,
) -> dict:
    """在文件中搜索文本。"""
    ft = _get_file_tools()
    result = ft.search_content(query, search_path, file_pattern=file_pattern, max_results=max_results)
    return result.to_dict()


# ── 工具状态概览 ──────────────────────────────────────


@app.get("/tools/status")
def get_tools_status() -> dict:
    """获取工具系统的整体状态和统计信息。"""
    runner = _get_command_runner()
    history = runner.get_history(limit=1000)

    total_executions = len(runner._history)
    success_count = sum(1 for e in history if e["success"])
    failed_count = sum(1 for e in history if not e["success"])
    timeout_count = sum(1 for e in history if e.get("timed_out"))

    # 最近使用的工具
    tool_usage: dict[str, int] = {}
    for entry in history:
        name = entry.get("tool_name", "unknown") or "unknown"
        tool_usage[name] = tool_usage.get(name, 0) + 1

    return {
        "sandbox_enabled": True,
        "allowed_command_count": len(runner.sandbox.allowed_commands),
        "safety_filter": "restricted",
        "working_directory": str(runner.working_directory or ""),
        "timeout_seconds": runner.timeout_seconds,
        "statistics": {
            "total_executions": total_executions,
            "success_count": success_count,
            "failed_count": failed_count,
            "timeout_count": timeout_count,
            "success_rate": round(success_count / max(total_executions, 1), 3),
        },
        "recently_used_tools": sorted(tool_usage.items(), key=lambda x: -x[1])[:10],
        "history_size": len(runner._history),
    }
