from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agent.autonomy import choose_next_action
from app.agent.loop_helpers import (
    build_action_result_thought as _build_action_result_thought,
    build_autobio_memory as _build_autobio_memory,
    build_chain_consolidation as _build_chain_consolidation,
    build_chain_progress as _build_chain_progress,
    build_chain_transition as _build_chain_transition,
    build_goal_completion as _build_goal_completion,
    build_goal_focus as _build_goal_focus,
    build_goal_focus_summary as _build_goal_focus_summary,
    build_goal_title as _build_goal_title,
    build_inner_stage_memory as _build_inner_stage_memory,
    build_next_goal_title as _build_next_goal_title,
    build_proactive_message as _build_proactive_message,
    build_proactive_thought as _build_proactive_thought,
    build_self_programming_memory as _build_self_programming_memory,
    build_today_plan_completion_memory as _build_today_plan_completion_memory,
    build_today_plan_step_focus as _build_today_plan_step_focus,
    build_world_goal_start as _build_world_goal_start,
    build_world_goal_title as _build_world_goal_title,
    display_goal_title as _display_goal_title,
    find_latest_autobio_event as _find_latest_autobio_event,
    find_latest_inner_event as _find_latest_inner_event,
    find_latest_user_event as _find_latest_user_event,
    find_latest_world_event as _find_latest_world_event,
    is_generated_goal_id as _is_generated_goal_id,
    next_focus_mode as _next_focus_mode,
    sync_today_plan as _sync_today_plan,
    workspace_root as _workspace_root,
)
from app.domain.models import FocusMode, TodayPlanStepKind, TodayPlanStepStatus, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import GoalRepository, InMemoryGoalRepository
from app.memory.models import MemoryEntry, MemoryEvent, MemoryKind
from app.memory.repository import MemoryRepository
from app.planning.morning_plan import MorningPlanPlanner
from app.runtime import StateStore
from app.self_programming.executor import SelfProgrammingExecutor
from app.self_programming.llm_planner import LLMPlanner
from app.self_programming.planner import SelfProgrammingPlanner
from app.self_programming.service import SelfProgrammingService
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
        self_programming_service: SelfProgrammingService | None = None,
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

        # 构建自我编程服务：优先使用 LLMPlanner（如果提供了 gateway）
        if self_programming_service is not None:
            self.self_programming_service = self_programming_service
        else:
            rule_planner = SelfProgrammingPlanner(workspace_root=workspace_root)
            executor = SelfProgrammingExecutor(workspace_root)
            if gateway is not None:
                llm_planner = LLMPlanner(
                    gateway=gateway,
                    workspace_root=workspace_root,
                    fallback_planner=rule_planner,
                )
                planner = llm_planner  # type: ignore[assignment]
            else:
                planner = rule_planner  # type: ignore[assignment]
            self.self_programming_service = SelfProgrammingService(
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
        self_programming_state = self._advance_self_programming(state, recent_events, now)
        if self_programming_state is not None:
            return self_programming_state
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
            goal_title = _display_goal_title(
                None if not state.active_goal_ids else state.active_goal_ids[0],
                current_goal,
            )
            if goal_title is None:
                return state
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
            goal_title = _display_goal_title(
                None if not state.active_goal_ids else state.active_goal_ids[0],
                current_goal,
            )
            if goal_title is None:
                return state
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
                if not _is_generated_goal_id(goal_id):
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

    def _advance_self_programming(self, state, recent_events, now: datetime):
        if state.focus_mode == FocusMode.SELF_IMPROVEMENT:
            next_state = self.self_programming_service.tick_job(state)
            if next_state is None:
                return None
            if (
                state.self_programming_job is not None
                and next_state.self_programming_job is not None
                and state.self_programming_job.status != next_state.self_programming_job.status
                and next_state.self_programming_job.status.value in {"applied", "failed"}
            ):
                entry = MemoryEntry.create(
                    kind=MemoryKind.EPISODIC,
                    content=_build_self_programming_memory(next_state.self_programming_job),
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
            return self.state_store.set(next_state)

        next_state = self.self_programming_service.maybe_start_job(
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
            goal_title = _display_goal_title(state.active_goal_ids[0], current_goal)

        entry = MemoryEntry.create(
            kind=MemoryKind.EPISODIC,
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
