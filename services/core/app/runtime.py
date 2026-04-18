from pathlib import Path
from threading import Lock
from typing import Callable

from app.domain.models import BeingState, TodayPlan
from app.memory.repository import MemoryRepository
from app.utils.file_utils import read_json_file, write_json_file
from app.usecases.lifecycle import go_to_sleep, wake_up


class StateStore:
    def __init__(
        self,
        initial_state: BeingState | None = None,
        memory_repository: MemoryRepository | None = None,
        storage_path: Path | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._lock = Lock()
        self._memory_repository = memory_repository
        self._storage_path = storage_path
        self._on_change = on_change
        self._state = self._load_state(initial_state)

    def _normalize_state(self, state: BeingState) -> BeingState:
        today_plan = state.today_plan
        if today_plan is not None and not isinstance(today_plan, TodayPlan):
            today_plan = TodayPlan.model_validate(today_plan)

        return state.model_copy(
            update={
                "today_plan": today_plan,
            },
            deep=True,
        )

    def get(self) -> BeingState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def set(self, state: BeingState) -> BeingState:
        with self._lock:
            self._state = self._normalize_state(state)
            self._persist_state(self._state)
            self._notify_change()
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

    def _load_state(self, initial_state: BeingState | None) -> BeingState:
        if self._storage_path is not None and self._storage_path.exists():
            data = read_json_file(self._storage_path)
            return self._normalize_state(BeingState.model_validate(data))
        return self._normalize_state(initial_state or BeingState.default())

    def _persist_state(self, state: BeingState) -> None:
        if self._storage_path is None:
            return

        write_json_file(
            self._storage_path,
            state.model_dump(mode="json"),
            ensure_ascii=False,
            create_parent=True,
        )

    def set_on_change_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()
