from fastapi.testclient import TestClient

from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.main import app, get_goal_repository, get_memory_repository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


def test_post_wake_returns_awake_state():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    assert response.status_code == 200
    assert response.json()["mode"] == "awake"


def test_post_wake_uses_recent_autobio_for_first_thought():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        assert "第1步走到第3步" in response.json()["current_thought"]
    finally:
        app.dependency_overrides.clear()


def test_post_wake_selects_today_focus_goal_from_active_chain():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )
    goal_repository = InMemoryGoalRepository()
    ordinary_goal = goal_repository.save_goal(Goal(title="整理今天的桌面文件"))
    chain_goal = goal_repository.save_goal(
        Goal(
            title="继续推进：继续推进：整理今天的对话记忆",
            chain_id="chain-1",
            generation=2,
        )
    )

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["active_goal_ids"] == [chain_goal.id]
        assert "继续推进：继续推进：整理今天的对话记忆" in body["current_thought"]
        assert ordinary_goal.id not in body["active_goal_ids"]
    finally:
        app.dependency_overrides.clear()


def test_post_wake_builds_morning_plan_before_acting_on_focus_goal():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )
    goal_repository = InMemoryGoalRepository()
    chain_goal = goal_repository.save_goal(
        Goal(
            title="继续推进：继续推进：整理今天的对话记忆",
            chain_id="chain-1",
            generation=2,
        )
    )

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        thought = response.json()["current_thought"]
        assert "先回看" in thought
        assert "再决定" in thought
        assert chain_goal.title in thought
    finally:
        app.dependency_overrides.clear()


def test_options_wake_allows_cors_preflight():
    client = TestClient(app)
    response = client.options(
        "/lifecycle/wake",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
