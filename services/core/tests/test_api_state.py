from fastapi.testclient import TestClient

from app.domain.models import BeingState, FocusMode, WakeMode
from app.main import app, get_state_store
from app.runtime import StateStore


def test_get_state_returns_current_runtime_state():
    client = TestClient(app)

    wake_response = client.post("/lifecycle/wake")
    assert wake_response.status_code == 200

    response = client.get("/state")

    assert response.status_code == 200
    assert response.json()["mode"] == "awake"
    assert response.json()["focus_mode"] in {"autonomy", "morning_plan"}


def test_get_state_includes_self_programming_job():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.SELF_IMPROVEMENT,
            self_programming_job={
                "reason": "测试失败：状态面板没有展示自我编程状态。",
                "target_area": "ui",
                "status": "verifying",
                "spec": "补上自我编程状态展示。",
                "patch_summary": "已修改状态面板。",
                "verification": {
                    "commands": ["npm test -- --run src/components/StatusPanel.test.tsx"],
                    "passed": True,
                    "summary": "3 passed",
                },
            },
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.get("/state")
        body = response.json()

        assert response.status_code == 200
        assert body["focus_mode"] == "self_programming"
        assert body["self_programming_job"]["target_area"] == "ui"
        assert body["self_programming_job"]["verification"]["passed"] is True
    finally:
        app.dependency_overrides.clear()
