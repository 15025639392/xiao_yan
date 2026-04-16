from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.domain.models import BeingState, WakeMode
from app.main import app, get_goal_repository, get_memory_repository, get_morning_plan_draft_generator, get_state_store
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


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
        body = response.json()
        thought = body["current_thought"]
        assert body["focus_mode"] == "morning_plan"
        assert "先回看" in thought
        assert "再决定" in thought
        assert chain_goal.title in thought
        assert body["today_plan"]["goal_id"] == chain_goal.id
        assert body["today_plan"]["goal_title"] == chain_goal.title
        assert [step["content"] for step in body["today_plan"]["steps"]] == [
            f"回看“{chain_goal.title}”停在了哪里",
            "决定是继续推进还是先收束",
        ]
        assert [step["status"] for step in body["today_plan"]["steps"]] == ["pending", "pending"]
    finally:
        app.dependency_overrides.clear()


def test_post_wake_builds_action_step_for_actionable_goal():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(Goal(title="看看现在在哪个目录"))

    def override_goal_repository():
        return goal_repository

    app.dependency_overrides[get_goal_repository] = override_goal_repository

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["active_goal_ids"] == [goal.id]
        assert body["today_plan"]["steps"][0]["kind"] == "action"
        assert body["today_plan"]["steps"][0]["command"] == "pwd"
        assert body["today_plan"]["steps"][1]["kind"] == "reflect"
    finally:
        app.dependency_overrides.clear()


def test_post_wake_uses_generated_plan_draft_when_it_is_valid():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(Goal(title="看看现在在哪个目录"))

    class StubDraftGenerator:
        def generate(self, goal, recent_autobio=None):
            return [
                {"content": "先确认当前目录", "kind": "action", "command": "pwd"},
                {"content": "再决定下一步", "kind": "reflect"},
            ]

    def override_goal_repository():
        return goal_repository

    def override_morning_plan_draft_generator():
        return StubDraftGenerator()

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_morning_plan_draft_generator] = override_morning_plan_draft_generator

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert [step["content"] for step in body["today_plan"]["steps"]] == ["先确认当前目录", "再决定下一步"]
        assert body["today_plan"]["steps"][0]["command"] == "pwd"
    finally:
        app.dependency_overrides.clear()


def test_post_wake_does_not_expose_self_programming_job_or_cooldown():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.SLEEPING,
            self_programming_job={
                "reason": "测试失败：状态面板没有展示自我编程状态。",
                "target_area": "ui",
                "status": "applied",
                "spec": "补上自我编程状态展示。",
                "cooldown_until": "2026-04-05T12:00:00Z",
            },
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "awake"
        assert "self_programming_job" not in body
    finally:
        app.dependency_overrides.clear()


def test_post_wake_preserves_last_proactive_markers():
    marker_time = datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc)
    state_store = StateStore(
        BeingState(
            mode=WakeMode.SLEEPING,
            last_proactive_source="嗯我同意",
            last_proactive_at=marker_time,
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["last_proactive_source"] == "嗯我同意"
        assert body["last_proactive_at"] == "2026-04-05T09:00:00Z"
    finally:
        app.dependency_overrides.clear()


def test_post_sleep_does_not_expose_self_programming_job_or_cooldown():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            self_programming_job={
                "reason": "测试失败：状态面板没有展示自我编程状态。",
                "target_area": "ui",
                "status": "failed",
                "spec": "补上自我编程状态展示。",
                "cooldown_until": "2026-04-05T12:00:00Z",
            },
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/sleep")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "sleeping"
        assert "self_programming_job" not in body
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
