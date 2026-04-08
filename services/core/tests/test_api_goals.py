from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.admission import (
    GoalAdmissionService,
    GoalAdmissionStore,
    GoalCandidate,
    GoalCandidateSource,
)
from app.goals.models import Goal, GoalStatus
from app.goals.repository import InMemoryGoalRepository
from app.memory.models import MemoryEvent
from app.main import app, get_goal_admission_service, get_goal_repository, get_state_store
from app.runtime import StateStore


def test_get_goals_returns_saved_goals():
    repository = InMemoryGoalRepository()
    repository.save_goal(
        Goal(
            title="继续理解用户的睡眠作息",
            admission={
                "score": 0.82,
                "recommended_decision": "admit",
                "applied_decision": "admit",
                "reason": "user_score",
            },
        )
    )

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
        assert body["goals"][0]["admission"]["applied_decision"] == "admit"
        assert body["goals"][0]["admission"]["reason"] == "user_score"
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


def test_get_goal_admission_stats_returns_current_snapshot():
    repository = InMemoryGoalRepository()
    admission_service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="shadow",
    )

    def override_goal_repository():
        return repository

    def override_goal_admission_service():
        return admission_service

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_goal_admission_service] = override_goal_admission_service

    try:
        client = TestClient(app)
        response = client.get("/goals/admission/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "shadow"
        assert "today" in body
        assert "deferred_queue_size" in body
        assert body["admitted_stability_24h"] == {
            "stable": 0,
            "re_deferred": 0,
            "dropped": 0,
        }
        assert body["admitted_stability_24h_rate"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_goal_admission_candidates_returns_deferred_and_recent_snapshot():
    repository = InMemoryGoalRepository()
    admission_service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
        min_score=0.9,
        defer_score=0.4,
    )
    now = datetime(2026, 4, 7, 8, 0, tzinfo=timezone.utc)
    admission_service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户明天复盘",
            source_content="提醒用户明天复盘",
        ),
        now=now,
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    admission_service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：催用户现在就做决定",
            source_content="我应该催用户现在就选，不再给他自己想的空间",
        ),
        now=now + timedelta(minutes=1),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="用户边界：你别催我，我希望先自己想一想再决定",
                source_context="value_signal:boundary",
            )
        ],
    )
    due = admission_service.pop_due_candidate(now + timedelta(minutes=6))
    assert due is not None
    admission_service.evaluate_candidate(
        due,
        now=now + timedelta(minutes=6),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户明天复盘",
                source_context="value_signal:commitment",
            )
        ],
    )
    admission_service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="持续理解用户最近在意的话题：嗯",
            source_content="嗯",
        ),
        now=now + timedelta(minutes=7),
        active_goals=[],
        all_goals=[],
        recent_events=[MemoryEvent(kind="chat", role="user", content="嗯")],
    )

    def override_goal_repository():
        return repository

    def override_goal_admission_service():
        return admission_service

    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_goal_admission_service] = override_goal_admission_service

    try:
        client = TestClient(app)
        response = client.get("/goals/admission/candidates")
        assert response.status_code == 200
        body = response.json()
        assert body["deferred"][0]["candidate"]["title"] == "持续理解用户最近在意的话题：嗯"
        assert body["deferred"][0]["last_reason"] == "user_score"
        assert any(item["decision"] == "drop" for item in body["recent"])
        assert any(item["reason"].startswith("relationship_boundary:") for item in body["recent"])
        assert body["admitted"][0]["decision"] == "admit"
        assert body["admitted"][0]["candidate"]["retry_count"] == 1
        assert body["admitted"][0]["stability"] == "stable"
    finally:
        app.dependency_overrides.clear()
