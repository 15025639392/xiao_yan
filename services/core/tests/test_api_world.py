import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.domain.models import BeingState, FocusMode, WakeMode
from app.main import (
    _ensure_runtime_initialized,
    app,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)
from app.runtime import StateStore
from app.world.models import WorldState
from app.world.repository import InMemoryWorldRepository
from app.world.service import WorldStateService


def test_get_world_returns_current_world_snapshot_and_persists_it():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "goal_backed_attention",
                "title": "整理今天的对话记忆",
                "why_now": "这条线还在继续。",
            },
        )
    )
    world_repository = InMemoryWorldRepository()

    def override_state_store():
        return state_store

    def override_world_repository():
        return world_repository

    class FixedWorldStateService(WorldStateService):
        def bootstrap(
            self,
            being_state=None,
            now=None,
        ):
            return super().bootstrap(
                being_state=being_state,
                now=datetime(2026, 4, 4, 14, 0),
            )

    def override_world_state_service():
        return FixedWorldStateService()

    app.dependency_overrides[get_state_store] = override_state_store
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
        assert body["focus_tension"] == "medium"
        assert body["focus_stage"] == "start"
        assert body["focus_step"] == 1
        assert body["latest_event"] is None

        saved = world_repository.get_world_state()
        assert saved == WorldState.model_validate(body)
    finally:
        app.dependency_overrides.clear()


def test_get_world_uses_focus_subject_goal_binding():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "goal_backed_attention",
                "title": "整理今天的对话记忆",
                "why_now": "这条线还挂在眼前。",
            },
        )
    )
    world_repository = InMemoryWorldRepository()

    def override_state_store():
        return state_store

    def override_world_repository():
        return world_repository

    class FixedWorldStateService(WorldStateService):
        def bootstrap(
            self,
            being_state=None,
            now=None,
        ):
            return super().bootstrap(
                being_state=being_state,
                now=datetime(2026, 4, 4, 14, 0),
            )

    def override_world_state_service():
        return FixedWorldStateService()

    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_world_repository] = override_world_repository
    app.dependency_overrides[get_world_state_service] = override_world_state_service

    try:
        client = TestClient(app)
        response = client.get("/world")

        assert response.status_code == 200
        body = response.json()
        assert body["mood"] == "engaged"
        assert body["focus_tension"] == "medium"
        assert body["focus_stage"] == "start"
        assert body["focus_step"] == 1
    finally:
        app.dependency_overrides.clear()


def test_runtime_initialization_builds_world_snapshot_immediately(
    tmp_path: Path, monkeypatch
):
    state_path = tmp_path / "state.json"
    world_path = tmp_path / "world.json"
    palace_path = tmp_path / "mempalace"
    state_path.write_text(
        json.dumps(
            BeingState(
                mode=WakeMode.AWAKE,
                focus_mode=FocusMode.AUTONOMY,
                current_thought="我还惦记着今天的整理。",
            ).model_dump(mode="json"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STATE_STORAGE_PATH", str(state_path))
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
