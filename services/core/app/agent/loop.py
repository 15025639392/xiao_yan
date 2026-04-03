from app.memory.models import MemoryEvent
from app.agent.autonomy import choose_next_action
from app.domain.models import WakeMode
from app.memory.repository import MemoryRepository
from app.runtime import StateStore


class AutonomyLoop:
    def __init__(self, state_store: StateStore, memory_repository: MemoryRepository) -> None:
        self.state_store = state_store
        self.memory_repository = memory_repository

    def tick_once(self):
        state = self.state_store.get()
        if state.mode != WakeMode.AWAKE:
            return state

        recent_events = list(reversed(self.memory_repository.list_recent(limit=4)))
        action = choose_next_action(
            state=state,
            pending_goals=state.active_goal_ids,
            recent_events=[event.content for event in recent_events],
        )

        if action.kind == "reflect":
            thought = _build_proactive_thought(recent_events)
            updates = {"current_thought": thought}

            latest_user_event = _find_latest_user_event(recent_events)
            if (
                latest_user_event is not None
                and latest_user_event.content != state.last_proactive_source
            ):
                proactive_message = _build_proactive_message(latest_user_event.content)
                self.memory_repository.save_event(
                    MemoryEvent(
                        kind="chat",
                        role="assistant",
                        content=proactive_message,
                    )
                )
                updates["current_thought"] = proactive_message
                updates["last_proactive_source"] = latest_user_event.content

            next_state = state.model_copy(update=updates)
            return self.state_store.set(next_state)

        return state


def _build_proactive_thought(recent_events) -> str:
    if recent_events:
        return f"我在想刚才关于“{recent_events[-1].content}”的事。"
    return "我在整理现在的状态，看看要不要主动说点什么。"


def _find_latest_user_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "chat" and event.role == "user":
            return event
    return None


def _build_proactive_message(content: str) -> str:
    return f"我刚刚又想到了你提到的“{content}”。"
