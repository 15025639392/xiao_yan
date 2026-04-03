from threading import Lock

from app.domain.models import BeingState
from app.memory.repository import MemoryRepository
from app.usecases.lifecycle import go_to_sleep, wake_up


class StateStore:
    def __init__(
        self,
        initial_state: BeingState | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self._lock = Lock()
        self._state = initial_state or BeingState.default()
        self._memory_repository = memory_repository

    def get(self) -> BeingState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def set(self, state: BeingState) -> BeingState:
        with self._lock:
            self._state = state.model_copy(deep=True)
            return self._state.model_copy(deep=True)

    def wake(self) -> BeingState:
        recent_autobio = None
        if self._memory_repository is not None:
            recent_events = self._memory_repository.list_recent(limit=20)
            recent_autobio = next(
                (event.content for event in recent_events if event.kind == "autobio"),
                None,
            )
        return self.set(wake_up(recent_autobio=recent_autobio))

    def sleep(self) -> BeingState:
        return self.set(go_to_sleep())
