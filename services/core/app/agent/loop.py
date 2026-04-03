from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agent.autonomy import GoalFocusSummary, choose_next_action
from app.domain.models import WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import GoalRepository, InMemoryGoalRepository
from app.memory.models import MemoryEvent
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
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
    ) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.goal_repository = goal_repository or InMemoryGoalRepository()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.world_state_service = world_state_service or WorldStateService()

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        now = self.now_provider()
        recent_events = list(reversed(self.memory_repository.list_recent(limit=20)))
        state, transitioned = self._sync_goal_focus(state, now)
        if transitioned:
            return state
        world_state = self._world_state_for(state, now)
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
                self.memory_repository.save_event(
                    MemoryEvent(
                        kind="chat",
                        role="assistant",
                        content=proactive_message,
                    )
                )
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
                self.memory_repository.save_event(
                    MemoryEvent(
                        kind="chat",
                        role="assistant",
                        content=proactive_message,
                    )
                )
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
            next_state = state.model_copy(update={"active_goal_ids": active_goal_ids})
            return self.state_store.set(next_state), False

        return state, False

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

        self.memory_repository.save_event(
            MemoryEvent(
                kind="world",
                content=self.world_state_service.build_event(world_state, goal_title),
                created_at=now,
            )
        )


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
