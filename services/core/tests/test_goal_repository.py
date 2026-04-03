from pathlib import Path

from app.goals.models import Goal, GoalStatus
from app.goals.repository import FileGoalRepository, InMemoryGoalRepository


def test_in_memory_goal_repository_returns_active_goals():
    repository = InMemoryGoalRepository()
    active_goal = Goal(title="持续理解用户最近在意的话题：星星")
    done_goal = Goal(title="整理昨晚的聊天摘要", status=GoalStatus.COMPLETED)

    repository.save_goal(active_goal)
    repository.save_goal(done_goal)

    active_goals = repository.list_active_goals()

    assert [goal.title for goal in active_goals] == ["持续理解用户最近在意的话题：星星"]


def test_file_goal_repository_persists_goals_across_instances(tmp_path: Path):
    storage_path = tmp_path / "goals.json"

    writer = FileGoalRepository(storage_path)
    goal = Goal(title="继续回应用户关于夜空的话题")
    writer.save_goal(goal)

    reader = FileGoalRepository(storage_path)
    loaded_goals = reader.list_goals()

    assert len(loaded_goals) == 1
    assert loaded_goals[0].title == "继续回应用户关于夜空的话题"
