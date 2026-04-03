from datetime import datetime

from fastapi.testclient import TestClient

from app.domain.models import BeingState, WakeMode
from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.main import (
    app,
    get_goal_repository,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)
from app.runtime import StateStore
from app.world.models import WorldState
from app.world.repository import InMemoryWorldRepository
from app.world.service import WorldStateService


def test_get_world_returns_current_world_snapshot_and_persists_it():
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]))
    goal_repository = InMemoryGoalRepository()
    goal_repository.save_goal(Goal(id="goal-1", title="整理今天的对话记忆"))
    world_repository = InMemoryWorldRepository()

    def override_state_store():
        return state_store

    def override_goal_repository():
        return goal_repository

    def override_world_repository():
        return world_repository

    class FixedWorldStateService(WorldStateService):
        def bootstrap(self, being_state=None, focused_goals=None, now=None):
            return super().bootstrap(
                being_state=being_state,
                focused_goals=focused_goals,
                now=datetime(2026, 4, 4, 14, 0),
            )

    def override_world_state_service():
        return FixedWorldStateService()

    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_world_repository] = override_world_repository
    app.dependency_overrides[get_world_state_service] = override_world_state_service

    try:
        client = TestClient(app)
        response = client.get("/world")

        assert response.status_code == 200
        body = response.json()
        assert body["time_of_day"] in {"morning", "afternoon", "evening", "night"}
        assert body["energy"] in {"low", "medium", "high"}
        assert body["mood"] == "engaged"
        assert body["focus_tension"] == "high"

        saved = world_repository.get_world_state()
        assert saved == WorldState.model_validate(body)
    finally:
        app.dependency_overrides.clear()
