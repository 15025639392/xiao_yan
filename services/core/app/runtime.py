from threading import Lock

from app.domain.models import BeingState
from app.usecases.lifecycle import go_to_sleep, wake_up


class StateStore:
    def __init__(self, initial_state: BeingState | None = None) -> None:
        self._lock = Lock()
        self._state = initial_state or BeingState.default()

    def get(self) -> BeingState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def set(self, state: BeingState) -> BeingState:
        with self._lock:
            self._state = state.model_copy(deep=True)
            return self._state.model_copy(deep=True)

    def wake(self) -> BeingState:
        return self.set(wake_up())

    def sleep(self) -> BeingState:
        return self.set(go_to_sleep())
