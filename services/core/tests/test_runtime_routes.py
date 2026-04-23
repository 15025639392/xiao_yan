from fastapi.testclient import TestClient

from app.api.deps import get_state_store
from app.domain.models import BeingState, WakeMode, FocusMode, XhsWorkDomainState, XhsWorkStatus
from app.main import app
from app.runtime import StateStore


def test_patch_xhs_work_domain_from_reviewing_to_idle_consumes_draft():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.REVIEWING,
                    "pending_drafts": [
                        {
                            "draft_id": "draft-1",
                            "title": "高颜值巧克力怎么发",
                            "body": "先拍开箱第一眼。",
                            "status": "ready_for_review",
                        }
                    ],
                    "backlog_count": 1,
                    "review_session_id": "review-session",
                    "published_history": [],
                }
            ),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.patch(
            "/xhs-work-domain",
            json={"status": "idle"},
        )

        assert response.status_code == 200
        domain = state_store.get().xhs_work_domain
        assert domain is not None
        assert domain.state.status == XhsWorkStatus.IDLE
        assert domain.state.review_session_id == ""
        assert len(domain.state.pending_drafts) == 0
        assert len(domain.state.published_history) == 1
        assert domain.state.published_history[0]["title"] == "高颜值巧克力怎么发"
        assert domain.state.backlog_count == 0
    finally:
        app.dependency_overrides.clear()


def test_patch_xhs_work_domain_idle_does_not_consume_drafts_when_not_reviewing():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.BLOCKED,
                    "pending_drafts": [
                        {
                            "draft_id": "draft-1",
                            "title": "高颜值巧克力怎么发",
                            "body": "先拍开箱第一眼。",
                            "status": "pending",
                        }
                    ],
                    "backlog_count": 1,
                    "published_history": [],
                }
            ),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.patch(
            "/xhs-work-domain",
            json={"status": "idle"},
        )

        assert response.status_code == 200
        domain = state_store.get().xhs_work_domain
        assert domain is not None
        assert domain.state.status == XhsWorkStatus.IDLE
        assert len(domain.state.pending_drafts) == 1
        assert len(domain.state.published_history) == 0
        assert domain.state.backlog_count == 1
    finally:
        app.dependency_overrides.clear()


def test_get_xhs_work_domain_exposes_last_scouting_data():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.IDLE,
                    "pending_drafts": [],
                    "published_history": [],
                    "last_scouting_data": {
                        "topics": [{"topic": "#高颜值巧克力"}],
                        "activities": [],
                    },
                }
            ),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.get("/xhs-work-domain")

        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["state"]["last_scouting_data"] == {
            "topics": [{"topic": "#高颜值巧克力"}],
            "activities": [],
        }
    finally:
        app.dependency_overrides.clear()


def test_get_xhs_work_domain_initializes_light_science_defaults():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.get("/xhs-work-domain")

        assert response.status_code == 200
        body = response.json()
        assert body["profile"]["account_positioning"] == "数字生命式情绪关系轻科普"
        assert "情绪、关系和自我认知" in body["profile"]["target_audience"]
        assert "先接住再解释" in body["profile"]["expression_style"]
        assert body["profile"]["publish_mode"] == "manual"
    finally:
        app.dependency_overrides.clear()


def test_get_xhs_work_domain_exposes_blocked_fields():
    from datetime import datetime, timezone

    blocked_at = datetime.now(timezone.utc)
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.BLOCKED,
                    "pending_drafts": [],
                    "published_history": [],
                    "blocked_at": blocked_at.isoformat(),
                    "blocked_reason": "浏览器器官不可用",
                }
            ),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.get("/xhs-work-domain")

        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["state"]["blocked_reason"] == "浏览器器官不可用"
        assert body["state"]["blocked_at"] == blocked_at.isoformat()
    finally:
        app.dependency_overrides.clear()


def test_patch_xhs_work_domain_updates_pending_drafts():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.IDLE,
                    "pending_drafts": [
                        {
                            "draft_id": "draft-1",
                            "title": "旧标题",
                            "body": "旧正文",
                            "status": "pending",
                        }
                    ],
                    "backlog_count": 1,
                    "published_history": [],
                }
            ),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.patch(
            "/xhs-work-domain",
            json={
                "pending_drafts": [
                    {
                        "draft_id": "draft-1",
                        "title": "新标题",
                        "body": "新正文",
                        "status": "pending",
                    }
                ],
                "backlog_count": 1,
            },
        )

        assert response.status_code == 200
        domain = state_store.get().xhs_work_domain
        assert domain is not None
        assert len(domain.state.pending_drafts) == 1
        assert domain.state.pending_drafts[0]["title"] == "新标题"
        assert domain.state.pending_drafts[0]["body"] == "新正文"
    finally:
        app.dependency_overrides.clear()


def test_patch_xhs_work_domain_updates_publish_mode():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            xhs_work_domain=XhsWorkDomainState(),
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.patch(
            "/xhs-work-domain",
            json={"publish_mode": "auto"},
        )

        assert response.status_code == 200
        domain = state_store.get().xhs_work_domain
        assert domain is not None
        assert domain.profile.publish_mode.value == "auto"
    finally:
        app.dependency_overrides.clear()
