from fastapi.testclient import TestClient

from app.main import app


def test_post_wake_returns_awake_state():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    assert response.status_code == 200
    assert response.json()["mode"] == "awake"


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
