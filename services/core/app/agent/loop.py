from __future__ import annotations

from datetime import datetime, timedelta

from app.agent.autonomy import GoalFocusSummary, choose_next_action
from app.agent.focus_timeline import list_recent_events_for_loop as _list_recent_events_for_loop
from app.agent.focus_updates import (
    focus_command_update,
    focus_consolidate_update,
    focus_hold_update,
)
from app.agent.loop_helpers import (
    build_action_result_thought as _build_action_result_thought,
    build_autobio_memory as _build_autobio_memory,
    build_inner_stage_memory as _build_inner_stage_memory,
    build_proactive_message as _build_proactive_message,
    build_proactive_thought as _build_proactive_thought,
    find_latest_autobio_event as _find_latest_autobio_event,
    find_latest_inner_event as _find_latest_inner_event,
    find_latest_user_event as _find_latest_user_event,
    next_focus_mode as _next_focus_mode,
)
from app.domain.models import WakeMode
from app.memory.models import MemoryEntry, MemoryEvent, MemoryKind
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox, ToolSafetyLevel
from app.utils.local_time import get_local_now
from app.world.service import WorldStateService


class AutonomyLoop:
    REFLECTIVE_CHECKIN_INTERVAL = timedelta(minutes=10)

    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        now_provider=None,
        world_state_service: WorldStateService | None = None,
        command_runner: CommandRunner | None = None,
        gateway=None,
    ) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.now_provider = now_provider or get_local_now
        self.world_state_service = world_state_service or WorldStateService()
        self.command_runner = command_runner or CommandRunner(
            CommandSandbox.with_defaults(max_level=ToolSafetyLevel.SAFE)
        )
        self.gateway = gateway

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        now = self.now_provider()
        recent_events = _list_recent_events_for_loop(self.memory_repository, limit=20)
        state = self._sync_focus_mode(state)
        world_state = self._world_state_for(state, now)
        self._maybe_record_inner_stage_memory(state, recent_events, world_state, now)
        self._maybe_record_autobio_memory()

        cooldown_ready = (
            state.last_proactive_at is None
            or now - state.last_proactive_at >= timedelta(seconds=60)
        )
        focus_summary = self._focus_summary_for(state, world_state)
        action = choose_next_action(
            state=state,
            has_goal_backed_focus=state.focus_subject is not None,
            focus_summary=focus_summary,
            recent_events=[event.content for event in recent_events],
            cooldown_ready=cooldown_ready,
            now=now,
        )

        if action.kind == "idle":
            return state

        if action.kind == "act":
            focus_title = _resolve_focus_title(state)
            if focus_title is None:
                return state
            actionable_command = _action_command_for_focus(focus_title)
            if actionable_command is not None:
                result = self.command_runner.run(actionable_command)
                action_summary = _build_action_result_thought(focus_title, now, world_state, result)
                entry = MemoryEntry.create(
                    kind=MemoryKind.EPISODIC,
                    content=action_summary,
                    source_context="action",
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))
                next_state = state.model_copy(
                    update=focus_command_update(
                        focus_title=focus_title,
                        action_summary=action_summary,
                        result=result,
                        now=now,
                    )
                )
                return self.state_store.set(next_state)

            next_state = state.model_copy(
                update=focus_hold_update(
                    focus_title=focus_title,
                    world_state=world_state,
                    chain_progress=None,
                    now=now,
                )
            )
            return self.state_store.set(next_state)

        if action.kind == "consolidate":
            focus_title = _resolve_focus_title(state)
            if focus_title is None:
                return state
            next_state = state.model_copy(
                update=focus_consolidate_update(
                    focus_title=focus_title,
                    world_state=world_state,
                    chain_progress=None,
                    now=now,
                )
            )
            return self.state_store.set(next_state)

        if action.kind == "reflect":
            thought = _build_proactive_thought(recent_events, now, world_state)
            updates = {"current_thought": thought}
            proactive_message: str | None = None

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
                updates["current_thought"] = proactive_message
                updates["last_proactive_source"] = latest_user_event.content
                updates["last_proactive_at"] = now
            elif (
                latest_user_event is None
                and recent_events
                and (
                    state.last_proactive_at is None
                    or now - state.last_proactive_at >= self.REFLECTIVE_CHECKIN_INTERVAL
                )
            ):
                proactive_message = thought
                updates["last_proactive_at"] = now

            if proactive_message:
                entry = MemoryEntry.create(
                    kind=MemoryKind.CHAT_RAW,
                    content=proactive_message,
                    role="assistant",
                )
                self.memory_repository.save_event(MemoryEvent.from_entry(entry))

            next_state = state.model_copy(update=updates)
            return self.state_store.set(next_state)

        return state

    def _sync_focus_mode(self, state):
        next_focus_mode = _next_focus_mode(state.mode, state.focus_mode)
        if next_focus_mode == state.focus_mode:
            return state
        return self.state_store.set(
            state.model_copy(
                update={
                    "focus_mode": next_focus_mode,
                }
            )
        )

    def _world_state_for(self, state, now: datetime):
        return self.world_state_service.bootstrap(
            being_state=state,
            now=now,
        )

    def _focus_summary_for(self, state, world_state) -> GoalFocusSummary | None:
        focus_title = _resolve_focus_title(state)
        if focus_title is None:
            return None
        return GoalFocusSummary(
            goal_title=focus_title,
            stage=world_state.focus_stage if world_state.focus_stage != "none" else "direct",
        )

    def _maybe_record_inner_stage_memory(self, state, recent_events, world_state, now: datetime) -> None:
        if world_state.focus_stage == "none" or world_state.focus_step is None:
            return

        focus_title = _resolve_focus_title(state)
        if focus_title is None:
            return

        inner_memory = _build_inner_stage_memory(world_state, focus_title)
        latest_inner_event = _find_latest_inner_event(recent_events)
        if latest_inner_event is not None and latest_inner_event.content == inner_memory:
            return

        entry = MemoryEntry.create(
            kind=MemoryKind.EPISODIC,
            content=inner_memory,
            source_context="inner",
        )
        self.memory_repository.save_event(MemoryEvent.from_entry(entry))

    def _maybe_record_autobio_memory(self) -> None:
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


def _resolve_focus_title(state) -> str | None:
    if state.focus_subject is None:
        return None
    title = state.focus_subject.title.strip()
    return title or None


def _action_command_for_focus(focus_title: str) -> str | None:
    if "时间" in focus_title or "几点" in focus_title:
        return "date +%H:%M"
    if "目录" in focus_title or "文件" in focus_title:
        return "pwd"
    return None
