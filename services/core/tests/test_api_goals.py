from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import InMemoryGoalRepository
from app.main import app, get_goal_repository, get_state_store
from app.runtime import StateStore


def test_get_goals_returns_saved_goals():
    repository = InMemoryGoalRepository()
    repository.save_goal(Goal(title="继续理解用户的睡眠作息"))

    def override_goal_repository():
        return repository

    app.dependency_overrides[get_goal_repository] = override_goal_repository

    try:
        client = TestClient(app)
        response = client.get("/goals")
        assert response.status_code == 200
        body = response.json()
        assert body["goals"][0]["title"] == "继续理解用户的睡眠作息"
        assert body["goals"][0]["status"] == "active"
    finally:
        app.dependency_overrides.clear()


def test_post_goal_status_updates_goal():
    repository = InMemoryGoalRepository()
    goal = repository.save_goal(Goal(title="继续理解用户的睡眠作息"))
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))

    def override_goal_repository():
        return repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post(f"/goals/{goal.id}/status", json={"status": "paused"})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == goal.id
        assert body["status"] == "paused"
        assert repository.get_goal(goal.id).status == GoalStatus.PAUSED
        assert state_store.get().active_goal_ids == []
    finally:
        app.dependency_overrides.clear()


def test_post_completed_goal_keeps_focus_until_autonomy_acknowledges_it():
    repository = InMemoryGoalRepository()
    goal = repository.save_goal(Goal(title="继续理解用户的睡眠作息"))
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))

    def override_goal_repository():
        return repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post(f"/goals/{goal.id}/status", json={"status": "completed"})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == goal.id
        assert body["status"] == "completed"
        assert repository.get_goal(goal.id).status == GoalStatus.COMPLETED
        assert state_store.get().active_goal_ids == [goal.id]
    finally:
        app.dependency_overrides.clear()


def test_pausing_plan_goal_switches_focus_to_next_active_goal_and_rebuilds_plan():
    repository = InMemoryGoalRepository()
    first_goal = repository.save_goal(
        Goal(title="整理今天的对话记忆", created_at=datetime(2026, 4, 5, tzinfo=timezone.utc))
    )
    second_goal = repository.save_goal(
        Goal(
            title="继续理解用户的睡眠作息",
            created_at=datetime(2026, 4, 5, 0, 1, tzinfo=timezone.utc),
        )
    )
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.MORNING_PLAN,
            active_goal_ids=[first_goal.id, second_goal.id],
            today_plan={
                "goal_id": first_goal.id,
                "goal_title": first_goal.title,
                "steps": [{"content": f"把“{first_goal.title}”的轮廓理一下", "status": "pending"}],
            },
        )
    )

    def override_goal_repository():
        return repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post(f"/goals/{first_goal.id}/status", json={"status": "paused"})
        assert response.status_code == 200
        current_state = state_store.get()
        assert current_state.active_goal_ids == [second_goal.id]
        assert current_state.focus_mode == FocusMode.MORNING_PLAN
        assert current_state.today_plan is not None
        assert current_state.today_plan.goal_id == second_goal.id
        assert current_state.today_plan.goal_title == second_goal.title
    finally:
        app.dependency_overrides.clear()


def test_resuming_goal_makes_it_current_focus_and_rebuilds_plan():
    repository = InMemoryGoalRepository()
    first_goal = repository.save_goal(Goal(title="整理今天的对话记忆"))
    second_goal = repository.save_goal(
        Goal(title="继续理解用户的睡眠作息", status=GoalStatus.PAUSED)
    )
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=[first_goal.id],
            today_plan={
                "goal_id": first_goal.id,
                "goal_title": first_goal.title,
                "steps": [{"content": f"把“{first_goal.title}”的轮廓理一下", "status": "completed"}],
            },
        )
    )

    def override_goal_repository():
        return repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post(f"/goals/{second_goal.id}/status", json={"status": "active"})
        assert response.status_code == 200
        current_state = state_store.get()
        assert current_state.active_goal_ids == [second_goal.id, first_goal.id]
        assert current_state.focus_mode == FocusMode.MORNING_PLAN
        assert current_state.today_plan is not None
        assert current_state.today_plan.goal_id == second_goal.id
        assert [step.status for step in current_state.today_plan.steps] == ["pending", "pending"]
    finally:
        app.dependency_overrides.clear()
