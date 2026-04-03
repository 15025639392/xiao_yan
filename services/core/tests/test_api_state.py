from fastapi.testclient import TestClient

from app.main import app


def test_get_state_returns_current_runtime_state():
    client = TestClient(app)

    wake_response = client.post("/lifecycle/wake")
    assert wake_response.status_code == 200

    response = client.get("/state")

    assert response.status_code == 200
    assert response.json()["mode"] == "awake"
