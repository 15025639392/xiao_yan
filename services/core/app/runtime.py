import json
from pathlib import Path
from threading import Lock

from app.domain.models import BeingState, SelfImprovementJob, TodayPlan
from app.memory.repository import MemoryRepository
from app.usecases.lifecycle import go_to_sleep, wake_up


class StateStore:
    def __init__(
        self,
        initial_state: BeingState | None = None,
        memory_repository: MemoryRepository | None = None,
        storage_path: Path | None = None,
    ) -> None:
        self._lock = Lock()
        self._memory_repository = memory_repository
        self._storage_path = storage_path
        self._state = self._load_state(initial_state)

    def get(self) -> BeingState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def set(self, state: BeingState) -> BeingState:
        with self._lock:
            today_plan = state.today_plan
            if today_plan is not None and not isinstance(today_plan, TodayPlan):
                today_plan = TodayPlan.model_validate(today_plan)

            self_improvement_job = state.self_improvement_job
            if self_improvement_job is not None and not isinstance(
                self_improvement_job, SelfImprovementJob
            ):
                self_improvement_job = SelfImprovementJob.model_validate(self_improvement_job)

            self._state = state.model_copy(
                update={
                    "today_plan": today_plan,
                    "self_improvement_job": self_improvement_job,
                },
                deep=True,
            )
            self._persist_state(self._state)
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
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            return BeingState.model_validate(data)
        return initial_state or BeingState.default()

    def _persist_state(self, state: BeingState) -> None:
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
