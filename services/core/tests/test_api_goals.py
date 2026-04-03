from fastapi.testclient import TestClient

from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.main import app, get_goal_repository


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
