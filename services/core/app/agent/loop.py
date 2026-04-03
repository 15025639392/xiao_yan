from datetime import datetime, timedelta, timezone

from app.memory.models import MemoryEvent
from app.agent.autonomy import choose_next_action
from app.domain.models import WakeMode
from app.memory.repository import MemoryRepository
from app.runtime import StateStore


class AutonomyLoop:
    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        now_provider=None,
    ) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        now = self.now_provider()
        recent_events = list(reversed(self.memory_repository.list_recent(limit=4)))
        cooldown_ready = (
            state.last_proactive_at is None
            or now - state.last_proactive_at >= timedelta(seconds=60)
        )
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
            next_state = state.model_copy(
                update={
                    "current_thought": _build_goal_focus(state.active_goal_ids[0], now),
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


def _time_prefix(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上，"
    if 11 <= hour < 17:
        return "白天，"
    if 17 <= hour < 22:
        return "傍晚，"
    return "晚上，"
