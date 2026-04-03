from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol

from app.goals.models import Goal, GoalStatus


class GoalRepository(Protocol):
    def save_goal(self, goal: Goal) -> Goal:
        ...

    def list_goals(self) -> list[Goal]:
        ...

    def list_active_goals(self) -> list[Goal]:
        ...

    def get_goal(self, goal_id: str) -> Goal | None:
        ...

    def update_status(self, goal_id: str, status: GoalStatus) -> Goal | None:
        ...


class InMemoryGoalRepository:
    def __init__(self) -> None:
        self._goals: dict[str, Goal] = {}

    def save_goal(self, goal: Goal) -> Goal:
        self._goals[goal.id] = goal
        return goal

    def list_goals(self) -> list[Goal]:
        return sorted(self._goals.values(), key=lambda goal: goal.created_at)

    def list_active_goals(self) -> list[Goal]:
        return [goal for goal in self.list_goals() if goal.status == GoalStatus.ACTIVE]

    def get_goal(self, goal_id: str) -> Goal | None:
        return self._goals.get(goal_id)

    def update_status(self, goal_id: str, status: GoalStatus) -> Goal | None:
        goal = self._goals.get(goal_id)
        if goal is None:
            return None

        updated = goal.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._goals[goal_id] = updated
        return updated


class FileGoalRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save_goal(self, goal: Goal) -> Goal:
        goals = {item.id: item for item in self.list_goals()}
        goals[goal.id] = goal
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps([item.model_dump(mode="json") for item in goals.values()], ensure_ascii=False),
            encoding="utf-8",
        )
        return goal

    def list_goals(self) -> list[Goal]:
        if not self.storage_path.exists():
            return []
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        return [Goal.model_validate(item) for item in data]

    def list_active_goals(self) -> list[Goal]:
        return [goal for goal in self.list_goals() if goal.status == GoalStatus.ACTIVE]

    def get_goal(self, goal_id: str) -> Goal | None:
        for goal in self.list_goals():
            if goal.id == goal_id:
                return goal
        return None

    def update_status(self, goal_id: str, status: GoalStatus) -> Goal | None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        updated = goal.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self.save_goal(updated)
