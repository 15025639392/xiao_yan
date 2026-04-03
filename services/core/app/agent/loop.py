from datetime import datetime, timedelta, timezone

from app.memory.models import MemoryEvent
from app.agent.autonomy import choose_next_action
from app.domain.models import WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import GoalRepository, InMemoryGoalRepository
from app.memory.repository import MemoryRepository
from app.runtime import StateStore


class AutonomyLoop:
    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        goal_repository: GoalRepository | None = None,
        now_provider=None,
    ) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.goal_repository = goal_repository or InMemoryGoalRepository()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        now = self.now_provider()
        recent_events = list(reversed(self.memory_repository.list_recent(limit=4)))
        state = self._sync_goal_focus(state, now)
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
                goal = self.goal_repository.save_goal(
                    Goal(
                        title=_build_goal_title(latest_user_event.content),
                        source=latest_user_event.content,
                    )
                )
                proactive_message = _build_proactive_message(
                    latest_user_event.content,
                    now,
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

        action = choose_next_action(
            state=state,
            pending_goals=state.active_goal_ids,
            recent_events=[event.content for event in recent_events],
            cooldown_ready=cooldown_ready,
            now=now,
        )

        if action.kind == "idle":
            return state

        if action.kind == "act":
            current_goal = self.goal_repository.get_goal(state.active_goal_ids[0])
            goal_title = current_goal.title if current_goal is not None else state.active_goal_ids[0]
            next_state = state.model_copy(
                update={
                    "current_thought": _build_goal_focus(goal_title, now),
                }
            )
            return self.state_store.set(next_state)

        if action.kind == "reflect":
            thought = _build_proactive_thought(recent_events, now)
            updates = {"current_thought": thought}

            latest_user_event = _find_latest_user_event(recent_events)
            if (
                latest_user_event is not None
                and latest_user_event.content != state.last_proactive_source
            ):
                proactive_message = _build_proactive_message(
                    latest_user_event.content,
                    now,
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
                next_state = state.model_copy(
                    update={
                        "active_goal_ids": active_goal_ids,
                        "current_thought": _build_goal_completion(goal.title, now),
                        "last_proactive_source": goal.source or state.last_proactive_source,
                        "last_proactive_at": now,
                    }
                )
                return self.state_store.set(next_state)

        if active_goal_ids != state.active_goal_ids:
            next_state = state.model_copy(update={"active_goal_ids": active_goal_ids})
            return self.state_store.set(next_state)

        return state


def _build_proactive_thought(recent_events, now: datetime) -> str:
    prefix = _time_prefix(now)
    if recent_events:
        return f"{prefix}我在想刚才关于“{recent_events[-1].content}”的事。"
    return f"{prefix}我在整理现在的状态，看看要不要主动说点什么。"


def _find_latest_user_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "chat" and event.role == "user":
            return event
    return None


def _build_proactive_message(content: str, now: datetime) -> str:
    return f"{_time_prefix(now)}我刚刚又想到了你提到的“{content}”。"


def _build_goal_focus(goal: str, now: datetime) -> str:
    return f"{_time_prefix(now)}我还惦记着“{goal}”，想继续把它推进。"


def _build_goal_completion(goal: str, now: datetime) -> str:
    return f"{_time_prefix(now)}我把“{goal}”先收住了。"


def _build_goal_title(content: str) -> str:
    return f"持续理解用户最近在意的话题：{content[:24]}"


def _time_prefix(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上，"
    if 11 <= hour < 17:
        return "白天，"
    if 17 <= hour < 22:
        return "傍晚，"
    return "晚上，"
