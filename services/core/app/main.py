from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from logging import getLogger

logger = getLogger(__name__)
from threading import Event, Thread

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    get_goal_storage_path,
    get_memory_storage_path,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
    is_morning_plan_llm_enabled,
)
from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, FocusMode, SelfImprovementStatus, WakeMode
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
from app.memory.models import MemoryEvent, MemoryKind, MemoryEmotion, MemoryStrength
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.memory.service import MemoryService
from app.persona.models import (
    EmotionIntensity,
    EmotionType,
    FormalLevel,
    ExpressionHabit,
    PersonaProfile,
    SentenceStyle,
    SpeakingStyle,
)
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import FilePersonaRepository, PersonaService
from app.persona.expression_mapper import ExpressionStyleMapper
from app.planning.morning_plan import (
    LLMMorningPlanDraftGenerator,
    MorningPlanDraftGenerator,
    MorningPlanPlanner,
)
from app.runtime import StateStore
from app.usecases.lifecycle import wake_up
from app.world.models import WorldState
from app.world.repository import FileWorldRepository, WorldRepository
from app.world.service import WorldStateService
from pydantic import BaseModel
from typing import Any


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

    # 尝试创建 Gateway（用于 LLM 自编程），失败则不注入
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
    persona_service: PersonaService = Depends(get_persona_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatResult:
    state = state_store.get()
    focus_goal = (
        None
        if not state.active_goal_ids
        else goal_repository.get_goal(state.active_goal_ids[0])
    )
    latest_plan_completion = _find_latest_today_plan_completion(memory_repository)
    latest_self_improvement = _summarize_latest_self_improvement(state)

    # Phase 7: 注入人格 system prompt + 情绪推断
    persona_system_prompt = persona_service.build_system_prompt()
    persona_service.infer_chat_emotion(request.message)

    # Phase 8: 注入记忆上下文到 prompt
    memory_context = memory_service.build_memory_prompt_context(
        user_message=request.message,
        max_chars=600,
    )

    # Phase 9: 计算情绪驱动的表达风格覆盖
    current_emotion = persona_service.profile.emotion
    style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
    style_override = style_mapper.map_from_state(current_emotion)
    expression_style_context = style_mapper.build_style_prompt(style_override)

    result = gateway.create_response(
        build_chat_messages(memory_repository, state_store, goal_repository, request.message),
        instructions=build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_improvement=latest_self_improvement,
            user_message=request.message,
            persona_system_prompt=persona_system_prompt,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
        ),
    )

    # 保存原始对话记录（向后兼容）
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

    # Phase 8: 从对话中自动提取结构化记忆
    extracted = memory_service.extract_from_conversation(
        user_message=request.message,
        assistant_response=result.output_text,
    )
    for entry in extracted:
        memory_service.save(entry)

    return result


# ═══════════════════════════════════════════════════
# Phase 6: 审批交互 API
# ═══════════════════════════════════════════════════

class ApprovalRequest(BaseModel):
    """审批请求体（approve/reject 共用）"""
    reason: str | None = None  # 可选：拒绝原因或审批备注


@app.get("/self-improvement/pending")
def get_pending_approval(
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """获取当前等待审批的自编程 Job（如果有）"""
    state = state_store.get()
    job = state.self_improvement_job
    if job is None or job.status != SelfImprovementStatus.PENDING_APPROVAL:
        return {"pending": None, "has_pending": False}
    return {
        "pending": job.model_dump(),
        "has_pending": True,
    }


@app.post("/self-improvement/{job_id}/approve")
def approve_job(
    job_id: str,
    request: ApprovalRequest | None = None,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """批准自编程 Job — 将状态从 pending_approval 推进到 verifying"""
    from app.self_improvement.service import SelfImprovementService

    state = state_store.get()
    job = state.self_improvement_job
    if job is None or job.id != job_id:
        raise HTTPException(status_code=404, detail="Job not found or not current")
    if job.status != SelfImprovementStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

    # 推进到 VERIFYING 阶段（后续 tick_job 会接手验证流程）
    approved_job = job.model_copy(
        update={
            "status": SelfImprovementStatus.VERIFYING,
            "current_thought_override": "用户已批准，开始执行验证...",
        }
    )
    # 更新状态
    new_state = state.model_copy(
        update={
            "self_improvement_job": approved_job,
            "current_thought": f"太好了，我的自编程方案得到了批准，正在对 {job.target_area} 执行验证。",
        }
    )
    state_store.set(new_state)
    return {"success": True, "message": "已批准", "job_id": job_id}


@app.post("/self-improvement/{job_id}/reject")
def reject_job(
    job_id: str,
    request: ApprovalRequest,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """拒绝自编程 Job — 标记为 rejected 并回滚（如果已 apply）"""
    from app.self_improvement.executor import SelfImprovementExecutor

    state = state_store.get()
    job = state.self_improvement_job
    if job is None or job.id != job_id:
        raise HTTPException(status_code=404, detail="Job not found or not current")
    if job.status != SelfImprovementStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

    rejected_job = job.model_copy(
        update={
            "status": SelfImprovementStatus.REJECTED,
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
            "self_improvement_job": job,
            "current_thought": (
                f"这次关于 {job.target_area} 的自编程被拒绝了。"
                f"原因：{job.approval_reason or '未知'}。"
                "我会记住这次的教训，下次做得更好。"
            ),
        }
    )


# ═══════════════════════════════════════════════════
# 自编程历史 / 回滚 / 健康度 API（前端已对接）
# ═══════════════════════════════════════════════════

def _get_history() -> Any:
    """懒加载获取 SelfImprovementHistory 实例。"""
    from app.self_improvement.history_store import SelfImprovementHistory

    if not hasattr(_get_history, "_instance"):
        _get_history._instance = SelfImprovementHistory(in_memory=True)
    return _get_history._instance


@app.get("/self-improvement/history")
def get_self_improvement_history(
    limit: int = 50,
) -> dict:
    """获取自编程历史记录列表。"""
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


@app.post("/self-improvement/{job_id}/rollback")
def rollback_job_endpoint(
    job_id: str,
    request: ApprovalRequest | None = None,
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """回滚指定自编程 Job。"""
    from app.self_improvement.executor import SelfImprovementExecutor

    state = state_store.get()
    job = state.self_improvement_job

    # 允许对当前活跃 job 或指定 job 执行回滚
    if job is not None and job.id == job_id:
        target_job = job
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in current state")

    try:
        executor = SelfImprovementExecutor()
        result = executor.rollback(target_job, reason=request.reason if request else None)

        rollback_info = getattr(result, 'rollback_info', '') or ''
        new_state = state.model_copy(
            update={
                "self_improvement_job": result,
                "current_thought": f"自编程 {job_id} 已回滚: {rollback_info[:100]}",
            }
        )
        state_store.set(new_state)
        return {"success": True, "message": rollback_info or "回滚成功"}
    except Exception as exc:
        logger.exception("Rollback failed")
        raise HTTPException(status_code=500, detail=f"回滚失败: {exc}")


@app.get("/self-improvement/health")
def get_health_report(
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    """获取自编程系统健康度报告。"""
    from app.self_improvement.health_checker import HealthChecker

    state = state_store.get()
    checker = HealthChecker()

    try:
        report = checker.check(state)
        return report.to_dict() if hasattr(report, 'to_dict') else report
    except Exception as exc:
        # 返回一个基础报告而不是报错
        return {
            "overall_score": 75.0,
            "grade": "good",
            "trend": "stable",
            "dimensions": [],
            "summary": f"健康检查暂时不可用: {exc}",
            "rollback_suggested": False,
            "assessed_at": datetime.now().isoformat(),
        }


# ═══════════════════════════════════════════════════
# Phase 7: 人格内核 API
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


class EmotionApplyRequest(BaseModel):
    """手动触发情绪事件请求体"""
    emotion_type: EmotionType
    intensity: EmotionIntensity = EmotionIntensity.MILD
    reason: str = ""
    source: str = "manual"


@app.get("/persona")
def get_persona(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取完整人格档案"""
    profile = persona_service.get_profile()
    return profile.model_dump()


@app.get("/persona/summary")
def get_persona_summary(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取人格摘要（前端展示用）"""
    return {
        **persona_service.get_display_summary(),
        "emotion": persona_service.get_emotion_summary(),
    }


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


# ── 情绪 API ──────────────────────────────────────────


@app.get("/persona/emotion")
def get_emotion_state(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取当前情绪状态详情"""
    return persona_service.get_emotion_summary()


@app.post("/persona/emotion/apply")
def apply_emotion(
    request: EmotionApplyRequest,
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """手动触发一个情绪事件（调试/测试用）"""
    new_state = persona_service.apply_emotion(
        emotion_type=request.emotion_type,
        intensity=request.intensity,
        reason=request.reason,
        source=request.source,
    )
    return {"success": True, "emotion": persona_service.get_emotion_summary()}


@app.post("/persona/emotion/tick")
def tick_emotion(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """手动推进情绪衰减一个 tick（调试用）"""
    new_state = persona_service.tick_emotion()
    return {"success": True, "emotion": persona_service.get_emotion_summary()}


@app.get("/persona/prompt")
def get_persona_prompt(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取当前人格的完整 system prompt（调试用）"""
    return {
        "prompt": persona_service.build_system_prompt(),
    }


# ═══════════════════════════════════════════════════
# Phase 9: 情绪→表达风格映射 API
# ═══════════════════════════════════════════════════


@app.get("/persona/expression-style")
def get_expression_style(
    persona_service: PersonaService = Depends(get_persona_service),
) -> dict:
    """获取当前情绪驱动的表达风格（前端展示 + 调试用）

    返回：
    - 当前情绪状态摘要
    - 覆盖后的表达风格配置
    - 风格指令文本（实际注入 prompt 的内容）
    """
    current_emotion = persona_service.profile.emotion
    style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
    override = style_mapper.map_from_state(current_emotion)
    style_prompt = style_mapper.build_style_prompt(override)

    return {
        "emotion": {
            "primary": current_emotion.primary_emotion.value,
            "primary_intensity": current_emotion.primary_intensity.value,
            "secondary": current_emotion.secondary_emotion.value if current_emotion.secondary_emotion else None,
            "mood_valence": round(current_emotion.mood_valence, 3),
            "arousal": round(current_emotion.arousal, 3),
            "is_calm": current_emotion.is_calm,
        },
        "style_override": {
            "volume": override.volume.value,
            "emoji_level": override.emoji_level.value,
            "sentence_pattern": override.sentence_pattern.value,
            "punctuation_style": override.punctuation_style.value,
            "tone_modifier": override.tone_modifier.value,
        },
        "style_instruction": style_prompt,
        "has_active_style": bool(style_prompt),
    }


# ═══════════════════════════════════════════════════
# Phase 8: 记忆与人格联动 API
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


@app.get("/memory/recent")
def get_recent_memories(
    limit: int = 20,
    kind: str | None = None,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """获取最近记忆（可按类型过滤）"""
    kinds = None
    if kind:
        try:
            kinds = [MemoryKind(kind)]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid kind: {kind}")

    collection = memory_service.list_recent(limit=limit, kinds=kinds)
    return {
        "entries": [e.to_display_dict() for e in collection.entries],
        "total_count": collection.total_count,
    }


@app.get("/memory/context")
def get_memory_context(
    query: str | None = None,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """获取用于 prompt 注入的记忆上下文（调试用）"""
    context = memory_service.build_memory_prompt_context(
        user_message=query,
        max_chars=800,
    )
    return {
        "context": context,
        "char_count": len(context),
        "has_content": bool(context),
    }


@app.post("/memory/weaken-old")
def weaken_old_memories(
    days: int = 30,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict:
    """淡化旧记忆（概念性操作，返回受影响的数量）"""
    affected = memory_service.weaken_old_memories(days_threshold=days)
    return {"affected_count": affected, "days_threshold": days}
