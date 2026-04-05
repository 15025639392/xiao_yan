from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agent.autonomy import GoalFocusSummary, choose_next_action
from app.domain.models import FocusMode, TodayPlanStepKind, TodayPlanStepStatus, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import GoalRepository, InMemoryGoalRepository
from app.memory.models import MemoryEntry, MemoryEvent, MemoryKind
from app.memory.repository import MemoryRepository
from app.planning.morning_plan import MorningPlanPlanner
from app.runtime import StateStore
from app.self_improvement.executor import SelfImprovementExecutor
from app.self_improvement.llm_planner import LLMPlanner
from app.self_improvement.planner import SelfImprovementPlanner
from app.self_improvement.service import SelfImprovementService
from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox, ToolSafetyLevel
from app.world.service import WorldStateService


class AutonomyLoop:
    WORLD_EVENT_COOLDOWN = timedelta(minutes=30)

    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        goal_repository: GoalRepository | None = None,
        now_provider=None,
        world_state_service: WorldStateService | None = None,
        command_runner: CommandRunner | None = None,
        morning_plan_planner: MorningPlanPlanner | None = None,
        self_improvement_service: SelfImprovementService | None = None,
        gateway=None,
    ) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.goal_repository = goal_repository or InMemoryGoalRepository()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.world_state_service = world_state_service or WorldStateService()
        self.command_runner = command_runner or CommandRunner(
            CommandSandbox.with_defaults(max_level=ToolSafetyLevel.SAFE)
        )
        self.morning_plan_planner = morning_plan_planner or MorningPlanPlanner()
        workspace_root = _workspace_root()

        # 构建自编程服务：优先使用 LLMPlanner（如果提供了 gateway）
        if self_improvement_service is not None:
            self.self_improvement_service = self_improvement_service
        else:
            rule_planner = SelfImprovementPlanner(workspace_root=workspace_root)
            executor = SelfImprovementExecutor(workspace_root)
            if gateway is not None:
                llm_planner = LLMPlanner(
                    gateway=gateway,
                    workspace_root=workspace_root,
                    fallback_planner=rule_planner,
                )
                planner = llm_planner  # type: ignore[assignment]
            else:
                planner = rule_planner  # type: ignore[assignment]
            self.self_improvement_service = SelfImprovementService(
                planner=planner,  # type: ignore[arg-type]
                executor=executor,
            )

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        now = self.now_provider()
        recent_events = list(reversed(self.memory_repository.list_recent(limit=20)))
        state, transitioned = self._sync_goal_focus(state, now)
        if transitioned:
            return state
        state = self._sync_focus_mode(state)
        self_improvement_state = self._advance_self_improvement(state, recent_events, now)
        if self_improvement_state is not None:
            return self_improvement_state
        world_state = self._world_state_for(state, now)
        seeded_plan_state = self._advance_morning_plan(state, now, world_state)
        if seeded_plan_state is not None:
            return seeded_plan_state
        self._maybe_record_inner_stage_memory(state, recent_events, world_state, now)
        self._maybe_record_autobio_memory(now)
        cooldown_ready = (
            state.last_proactive_at is None
            or now - state.last_proactive_at >= timedelta(seconds=60)
        )

        if not state.active_goal_ids and cooldown_ready:
            latest_user_event = _find_latest_user_event(recent_events)
            if (
                latest_user_event is not None
                and latest_user_event.content != state.last_proactive_source
            ):
                goal_world_state = self.world_state_service.bootstrap(
                    being_state=state.model_copy(update={"active_goal_ids": ["pending-goal"]}),
                    focused_goals=[Goal(title=_build_goal_title(latest_user_event.content))],
                    now=now,
                )
                goal = self.goal_repository.save_goal(
                    Goal(
                        title=_build_goal_title(latest_user_event.content),
                        source=latest_user_event.content,
                    )
                )
                proactive_message = _build_proactive_message(
                    latest_user_event.content,
                    now,
                    goal_world_state,
                )
                entry = MemoryEntry.create(
                    kind=MemoryKind.CHAT_RAW,
                    content=proactive_message,
                    role="assistant",
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
                next_state = state.model_copy(
                    update={
                        "active_goal_ids": [goal.id],
                        "current_thought": proactive_message,
                        "last_proactive_source": latest_user_event.content,
                        "last_proactive_at": now,
                    }
                )
                return self.state_store.set(next_state)

            latest_world_event = _find_latest_world_event(recent_events)
            if (
                latest_world_event is not None
                and latest_world_event.content != state.last_proactive_source
            ):
                goal = self.goal_repository.save_goal(
                    Goal(
                        title=_build_world_goal_title(latest_world_event.content),
                        source=latest_world_event.content,
                        chain_id=uuid4().hex,
                    )
                )
                proactive_thought = _build_world_goal_start(
                    latest_world_event.content,
                    now,
                    world_state,
                )
                next_state = state.model_copy(
                    update={
                        "active_goal_ids": [goal.id],
                        "current_thought": proactive_thought,
                        "last_proactive_source": latest_world_event.content,
                        "last_proactive_at": now,
                    }
                )
                return self.state_store.set(next_state)

        self._maybe_record_world_event(state, recent_events, world_state, now)

        current_goal = (
            None
            if not state.active_goal_ids
            else self.goal_repository.get_goal(state.active_goal_ids[0])
        )
        focus_summary = (
            None
            if current_goal is None
            else _build_goal_focus_summary(self.goal_repository, current_goal)
        )
        action = choose_next_action(
            state=state,
            pending_goals=state.active_goal_ids,
            focus_summary=focus_summary,
            recent_events=[event.content for event in recent_events],
            cooldown_ready=cooldown_ready,
            now=now,
        )

        if action.kind == "idle":
            return state

        if action.kind == "act":
            goal_title = current_goal.title if current_goal is not None else state.active_goal_ids[0]
            actionable_command = self.morning_plan_planner.action_command_for_goal(goal_title)
            if actionable_command is not None:
                result = self.command_runner.run(actionable_command)
                action_summary = _build_action_result_thought(goal_title, now, world_state, result)
                entry = MemoryEntry.create(
                    kind=MemoryKind.EPISODIC,
                    content=action_summary,
                    source_context="action",
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
                next_state = state.model_copy(
                    update={
                        "current_thought": action_summary,
                        "last_action": result,
                    }
                )
                return self.state_store.set(next_state)
            chain_progress = (
                None if current_goal is None else _build_chain_progress(self.goal_repository, current_goal)
            )
            next_state = state.model_copy(
                update={
                    "current_thought": _build_goal_focus(goal_title, now, world_state, chain_progress),
                }
            )
            return self.state_store.set(next_state)

        if action.kind == "consolidate":
            goal_title = current_goal.title if current_goal is not None else state.active_goal_ids[0]
            chain_progress = (
                None if current_goal is None else _build_chain_progress(self.goal_repository, current_goal)
            )
            next_state = state.model_copy(
                update={
                    "current_thought": _build_chain_consolidation(
                        goal_title,
                        now,
                        world_state,
                        chain_progress,
                    ),
                }
            )
            return self.state_store.set(next_state)

        if action.kind == "reflect":
            thought = _build_proactive_thought(recent_events, now, world_state)
            updates = {"current_thought": thought}

            latest_user_event = _find_latest_user_event(recent_events)
            if (
                latest_user_event is not None
                and latest_user_event.content != state.last_proactive_source
            ):
                proactive_message = _build_proactive_message(
                    latest_user_event.content,
                    now,
                    world_state,
                )
                entry = MemoryEntry.create(
                    kind=MemoryKind.CHAT_RAW,
                    content=proactive_message,
                    role="assistant",
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
                updates["current_thought"] = proactive_message
                updates["last_proactive_source"] = latest_user_event.content
                updates["last_proactive_at"] = now

            next_state = state.model_copy(update=updates)
            return self.state_store.set(next_state)

        return state

    def _sync_goal_focus(self, state, now: datetime):
        active_goal_ids: list[str] = []

        for goal_id in state.active_goal_ids:
            goal = self.goal_repository.get_goal(goal_id)
            if goal is None:
                active_goal_ids.append(goal_id)
                continue

            if goal.status == GoalStatus.ACTIVE:
                active_goal_ids.append(goal_id)
                continue

            if goal.status == GoalStatus.COMPLETED:
                world_state = self.world_state_service.bootstrap(
                    being_state=state,
                    focused_goals=[goal],
                    now=now,
                )
                next_goal = None
                if goal.chain_id:
                    next_goal = self.goal_repository.save_goal(
                        Goal(
                            title=_build_next_goal_title(goal.title),
                            source=goal.source,
                            chain_id=goal.chain_id,
                            parent_goal_id=goal.id,
                            generation=goal.generation + 1,
                        )
                    )
                chain_progress = (
                    None if next_goal is None else _build_chain_transition(self.goal_repository, next_goal)
                )
                next_state = state.model_copy(
                    update={
                        "active_goal_ids": (
                            [next_goal.id] if next_goal is not None else active_goal_ids
                        ),
                        "focus_mode": FocusMode.AUTONOMY,
                        "today_plan": None,
                        "current_thought": _build_goal_completion(
                            goal.title,
                            now,
                            world_state,
                            chain_progress=chain_progress,
                            next_goal_title=None if next_goal is None else next_goal.title,
                        ),
                        "last_proactive_source": goal.source or state.last_proactive_source,
                        "last_proactive_at": now,
                    }
                )
                return self.state_store.set(next_state), True

        if active_goal_ids != state.active_goal_ids:
            next_state = state.model_copy(
                update={
                    "active_goal_ids": active_goal_ids,
                    "today_plan": _sync_today_plan(state.today_plan, active_goal_ids),
                    "focus_mode": _next_focus_mode(
                        state.mode,
                        state.focus_mode,
                        _sync_today_plan(state.today_plan, active_goal_ids),
                    ),
                }
            )
            return self.state_store.set(next_state), False

        return state, False

    def _sync_focus_mode(self, state):
        next_today_plan = _sync_today_plan(state.today_plan, state.active_goal_ids)
        next_focus_mode = _next_focus_mode(state.mode, state.focus_mode, next_today_plan)
        if next_today_plan == state.today_plan and next_focus_mode == state.focus_mode:
            return state
        return self.state_store.set(
            state.model_copy(
                update={
                    "today_plan": next_today_plan,
                    "focus_mode": next_focus_mode,
                }
            )
        )

    def _advance_morning_plan(self, state, now: datetime, world_state):
        if state.focus_mode != FocusMode.MORNING_PLAN:
            return None
        if state.today_plan is None or not state.today_plan.steps:
            return None

        next_pending_index = next(
            (
                index
                for index, step in enumerate(state.today_plan.steps)
                if step.status == TodayPlanStepStatus.PENDING
            ),
            None,
        )
        if next_pending_index is None:
            next_state = state.model_copy(update={"focus_mode": FocusMode.AUTONOMY})
            return self.state_store.set(next_state)

        next_step = state.today_plan.steps[next_pending_index]
        if state.today_plan.goal_id not in state.active_goal_ids:
            return None

        next_steps = [
            step.model_copy(update={"status": TodayPlanStepStatus.COMPLETED})
            if index == next_pending_index
            else step
            for index, step in enumerate(state.today_plan.steps)
        ]
        next_focus_mode = (
            FocusMode.AUTONOMY
            if all(step.status == TodayPlanStepStatus.COMPLETED for step in next_steps)
            else FocusMode.MORNING_PLAN
        )
        updates = {
            "focus_mode": next_focus_mode,
            "today_plan": state.today_plan.model_copy(update={"steps": next_steps}),
        }
        if next_step.kind == TodayPlanStepKind.ACTION and next_step.command is not None:
            result = self.command_runner.run(next_step.command)
            action_summary = _build_action_result_thought(
                state.today_plan.goal_title,
                now,
                world_state,
                result,
            )
            entry = MemoryEntry.create(
                kind=MemoryKind.EPISODIC,
                content=action_summary,
                source_context="action",
            )
            self.memory_repository.save_event(MemoryEvent.from_entry(entry))
            updates["current_thought"] = action_summary
            updates["last_action"] = result
        else:
            updates["current_thought"] = _build_today_plan_step_focus(
                state.today_plan.goal_title,
                next_step.content,
                now,
                world_state,
            )
        if next_focus_mode == FocusMode.AUTONOMY:
            entry = MemoryEntry.create(
                kind=MemoryKind.EPISODIC,
                content=_build_today_plan_completion_memory(state.today_plan.goal_title),
                source_context="autobio",
            )
            self.memory_repository.save_event(MemoryEvent.from_entry(entry))
        next_state = state.model_copy(update=updates)
        return self.state_store.set(next_state)

    def _advance_self_improvement(self, state, recent_events, now: datetime):
        if state.focus_mode == FocusMode.SELF_IMPROVEMENT:
            next_state = self.self_improvement_service.tick_job(state)
            if next_state is None:
                return None
            if (
                state.self_improvement_job is not None
                and next_state.self_improvement_job is not None
                and state.self_improvement_job.status != next_state.self_improvement_job.status
                and next_state.self_improvement_job.status.value in {"applied", "failed"}
            ):
                entry = MemoryEntry.create(
                    kind=MemoryKind.EPISODIC,
                    content=_build_self_improvement_memory(next_state.self_improvement_job),
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
            return self.state_store.set(next_state)

        next_state = self.self_improvement_service.maybe_start_job(
            state,
            recent_events,
            now,
        )
        if next_state is None:
            return None
        return self.state_store.set(next_state)

    def _world_state_for(self, state, now: datetime):
        focused_goals = [
            goal
            for goal_id in state.active_goal_ids
            if (goal := self.goal_repository.get_goal(goal_id)) is not None
        ]
        return self.world_state_service.bootstrap(
            being_state=state,
            focused_goals=focused_goals,
            now=now,
        )

    def _maybe_record_world_event(self, state, recent_events, world_state, now: datetime) -> None:
        if _find_latest_user_event(recent_events) is not None:
            return

        latest_world_event = _find_latest_world_event(recent_events)
        if (
            latest_world_event is not None
            and now - latest_world_event.created_at < self.WORLD_EVENT_COOLDOWN
        ):
            return

        goal_title = None
        if state.active_goal_ids:
            current_goal = self.goal_repository.get_goal(state.active_goal_ids[0])
            goal_title = (
                current_goal.title if current_goal is not None else state.active_goal_ids[0]
            )

        entry = MemoryEntry.create(
            kind=MemoryKind.FACT,
            content=self.world_state_service.build_event(world_state, goal_title),
            source_context="world",
        )
        self.memory_repository.save_event(MemoryEvent.from_entry(entry))

    def _maybe_record_inner_stage_memory(self, state, recent_events, world_state, now: datetime) -> None:
        if world_state.focus_stage == "none" or world_state.focus_step is None:
            return

        current_goal = None
        if state.active_goal_ids:
            current_goal = self.goal_repository.get_goal(state.active_goal_ids[0])

        if current_goal is None or current_goal.chain_id is None:
            return

        goal_title = current_goal.title

        inner_memory = _build_inner_stage_memory(world_state, goal_title)
        latest_inner_event = _find_latest_inner_event(recent_events)
        if latest_inner_event is not None and latest_inner_event.content == inner_memory:
            return

        entry = MemoryEntry.create(
            kind=MemoryKind.EPISODIC,
            content=inner_memory,
            source_context="inner",
        )
        self.memory_repository.save_event(MemoryEvent.from_entry(entry))

    def _maybe_record_autobio_memory(self, now: datetime) -> None:
        recent_events = list(reversed(self.memory_repository.list_recent(limit=20)))
        inner_events = [event for event in recent_events if event.kind == "inner"]
        if len(inner_events) < 3:
            return

        autobio_memory = _build_autobio_memory(inner_events[-3:])
        latest_autobio_event = _find_latest_autobio_event(recent_events)
        if latest_autobio_event is not None and latest_autobio_event.content == autobio_memory:
            return

        entry = MemoryEntry.create(
            kind=MemoryKind.EPISODIC,
            content=autobio_memory,
            source_context="autobio",
        )
        self.memory_repository.save_event(MemoryEvent.from_entry(entry))


def _build_proactive_thought(recent_events, now: datetime, world_state) -> str:
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)
    if recent_events:
        return f"{prefix}{tone}我在想刚才关于“{recent_events[-1].content}”的事。"
    return f"{prefix}{tone}我在整理现在的状态，看看要不要主动说点什么。"


def _find_latest_user_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "chat" and event.role == "user":
            return event
    return None


def _find_latest_world_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "world":
            return event
    return None


def _find_latest_inner_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "inner":
            return event
    return None


def _find_latest_autobio_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "autobio":
            return event
    return None


def _build_proactive_message(content: str, now: datetime, world_state) -> str:
    return f"{_time_prefix(now)}{_world_tone(world_state)}我刚刚又想到了你提到的“{content}”。"


def _build_goal_focus(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return f"{_time_prefix(now)}{_world_tone(world_state)}我还惦记着“{goal}”，{progress}想继续把它推进。"


def _build_today_plan_step_focus(
    goal: str,
    step_content: str,
    now: datetime,
    world_state,
) -> str:
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我先按今天的计划，从第一步开始：{step_content}。"
    )


def _build_today_plan_completion_memory(goal: str) -> str:
    return f"我把今天的计划“{goal}”完整走完了，感觉这一轮心里更有数了。"


def _build_action_result_thought(goal: str, now: datetime, world_state, result) -> str:
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我刚为“{goal}”执行了 `{result.command}`，结果是：{result.output}。"
    )


def _build_goal_completion(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
    next_goal_title: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    if next_goal_title is not None:
        return (
            f"{_time_prefix(now)}{_world_tone(world_state)}"
            f"我把“{goal}”先收住了，{progress}接下来想继续“{next_goal_title}”。"
        )
    return f"{_time_prefix(now)}{_world_tone(world_state)}我把“{goal}”先收住了。"


def _build_chain_consolidation(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我想先回看一下，{progress}看看怎么把“{goal}”收束得更完整。"
    )


def _build_goal_title(content: str) -> str:
    return f"持续理解用户最近在意的话题：{content[:24]}"


def _build_world_goal_title(content: str) -> str:
    return f"继续消化自己刚经历的状态：{content[:24]}"


def _build_next_goal_title(goal_title: str) -> str:
    return f"继续推进：{goal_title[:24]}"


def _build_world_goal_start(content: str, now: datetime, world_state) -> str:
    return f"{_time_prefix(now)}{_world_tone(world_state)}我还在回味刚才那件事：“{content}”。"


def _build_inner_stage_memory(world_state, goal_title: str | None = None) -> str:
    stage_label = _focus_stage_label(world_state.focus_stage)
    goal_suffix = "" if goal_title is None else f"，还在围绕“{goal_title}”"
    return (
        f"我感觉自己已经走到第{world_state.focus_step}步，"
        f"正在进入{stage_label}{goal_suffix}。"
    )


def _build_autobio_memory(inner_events: list[MemoryEvent]) -> str:
    steps = [_extract_focus_step(event.content) for event in inner_events]
    rendered_steps = "、".join(f"第{step}步" for step in steps if step is not None)
    return f"我最近像是一路从{rendered_steps}走过来，开始学着把这些变化连成自己的经历。"


def _time_prefix(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上，"
    if 11 <= hour < 17:
        return "白天，"
    if 17 <= hour < 22:
        return "傍晚，"
    return "晚上，"


def _world_tone(world_state) -> str:
    if world_state.mood == "tired":
        return "我有点困，但"
    if world_state.mood == "calm":
        return "我心里松一点了，"
    if world_state.focus_tension == "high":
        return "我心里还绷着这件事，"
    if world_state.energy == "high":
        return "我现在挺清醒，"
    return ""


def _sync_today_plan(today_plan, active_goal_ids: list[str]):
    if today_plan is None:
        return None
    if today_plan.goal_id not in active_goal_ids:
        return None
    return today_plan


def _next_focus_mode(mode, current_focus_mode, today_plan):
    if mode != WakeMode.AWAKE:
        return FocusMode.SLEEPING
    if current_focus_mode == FocusMode.SELF_IMPROVEMENT:
        return FocusMode.SELF_IMPROVEMENT
    if today_plan is None:
        return FocusMode.AUTONOMY
    if any(step.status == TodayPlanStepStatus.PENDING for step in today_plan.steps):
        return FocusMode.MORNING_PLAN
    return (
        current_focus_mode
        if current_focus_mode == FocusMode.AUTONOMY
        else FocusMode.AUTONOMY
    )


def _build_chain_progress(goal_repository: GoalRepository, goal: Goal) -> str | None:
    summary = _summarize_chain(goal_repository, goal)
    if summary is None:
        return None
    return f"这条线已经走到第{summary.generation + 1}步了，"


def _build_chain_transition(goal_repository: GoalRepository, goal: Goal) -> str | None:
    summary = _summarize_chain(goal_repository, goal)
    if summary is None:
        return None
    return f"这条线已经接到第{summary.generation + 1}步了，"


def _build_self_improvement_memory(job) -> str:
    if job.status.value == "applied":
        return f"我刚完成了一次自我编程，补强了 {job.target_area}，并通过了验证。"
    return f"我刚尝试自我编程，但还没通过验证：{job.patch_summary or job.reason}"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _build_goal_focus_summary(
    goal_repository: GoalRepository,
    goal: Goal,
) -> GoalFocusSummary:
    if goal.chain_id is None:
        return GoalFocusSummary(goal_title=goal.title)

    chain_goals = [
        item for item in goal_repository.list_goals() if item.chain_id == goal.chain_id
    ]
    chain_length = len(chain_goals)
    generation = goal.generation
    stage = _chain_stage_for(generation)

    return GoalFocusSummary(
        goal_title=goal.title,
        chain_id=goal.chain_id,
        chain_length=chain_length,
        chain_generation=generation,
        stage=stage,
    )


def _summarize_chain(goal_repository: GoalRepository, goal: Goal):
    if goal.chain_id is None:
        return None

    chain_goals = sort_goals_by_generation(
        [item for item in goal_repository.list_goals() if item.chain_id == goal.chain_id]
    )
    if not chain_goals:
        return None

    highest_generation = max(item.generation for item in chain_goals)
    latest_generation_goals = [
        item for item in chain_goals if item.generation == highest_generation
    ]
    return sorted(
        latest_generation_goals,
        key=lambda item: _goal_status_priority(item.status),
    )[0]


def sort_goals_by_generation(goals: list[Goal]) -> list[Goal]:
    return sorted(goals, key=lambda goal: (goal.generation, goal.created_at))


def _goal_status_priority(status: GoalStatus) -> int:
    if status == GoalStatus.ACTIVE:
        return 0
    if status == GoalStatus.PAUSED:
        return 1
    if status == GoalStatus.COMPLETED:
        return 2
    return 3


def _chain_stage_for(generation: int) -> str:
    if generation >= 2:
        return "consolidate"
    if generation == 1:
        return "deepen"
    return "start"


def _focus_stage_label(stage: str) -> str:
    if stage == "consolidate":
        return "收束阶段"
    if stage == "deepen":
        return "深入阶段"
    if stage == "start":
        return "起步阶段"
    return "当前阶段"


def _extract_focus_step(content: str) -> int | None:
    marker = "第"
    suffix = "步"
    if marker not in content or suffix not in content:
        return None

    start = content.find(marker) + len(marker)
    end = content.find(suffix, start)
    if end <= start:
        return None

    step_text = content[start:end]
    if not step_text.isdigit():
        return None
    return int(step_text)
