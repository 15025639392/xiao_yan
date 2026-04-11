import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.main import (
    _ensure_runtime_initialized,
    app,
    get_goal_repository,
    get_memory_repository,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.world.models import WorldState
from app.world.repository import InMemoryWorldRepository
from app.world.service import WorldStateService


def test_get_world_returns_current_world_snapshot_and_persists_it():
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]))
    goal_repository = InMemoryGoalRepository()
    goal_repository.save_goal(Goal(id="goal-1", title="整理今天的对话记忆"))
    world_repository = InMemoryWorldRepository()
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="world",
            content="夜里很安静，我有点困，但还惦记着整理今天的对话记忆。",
        )
    )

    def override_state_store():
        return state_store

    def override_goal_repository():
        return goal_repository

    def override_world_repository():
        return world_repository

    def override_memory_repository():
        return memory_repository

    class FixedWorldStateService(WorldStateService):
        def bootstrap(
            self,
            being_state=None,
            focused_goals=None,
            now=None,
            latest_event=None,
            latest_event_at=None,
        ):
            return super().bootstrap(
                being_state=being_state,
                focused_goals=focused_goals,
                now=datetime(2026, 4, 4, 14, 0),
                latest_event=latest_event,
                latest_event_at=latest_event_at,
            )

    def override_world_state_service():
        return FixedWorldStateService()

    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_memory_repository] = override_memory_repository
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
        assert body["focus_stage"] == "start"
        assert body["focus_step"] == 1
        assert "整理今天的对话记忆" in body["latest_event"]

        saved = world_repository.get_world_state()
        assert saved == WorldState.model_validate(body)
    finally:
        app.dependency_overrides.clear()


def test_runtime_initialization_builds_world_snapshot_immediately(
    tmp_path: Path, monkeypatch
):
    state_path = tmp_path / "state.json"
    goal_path = tmp_path / "goals.json"
    world_path = tmp_path / "world.json"
    palace_path = tmp_path / "mempalace"
    state_path.write_text(
        json.dumps(
            BeingState(
                mode=WakeMode.AWAKE,
                focus_mode=FocusMode.AUTONOMY,
                current_thought="我还惦记着今天的整理。",
                active_goal_ids=[],
            ).model_dump(mode="json"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STATE_STORAGE_PATH", str(state_path))
    monkeypatch.setenv("GOAL_STORAGE_PATH", str(goal_path))
    monkeypatch.setenv("WORLD_STORAGE_PATH", str(world_path))
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(palace_path))

    target_app = FastAPI()
    _ensure_runtime_initialized(target_app)

    try:
        saved = target_app.state.world_repository.get_world_state()
        assert saved is not None
        assert saved.energy in {"low", "medium", "high"}
        assert saved.mood in {"calm", "engaged", "tired"}
    finally:
        target_app.state.stop_event.set()
        target_app.state.autonomy_thread.join(timeout=1.0)
