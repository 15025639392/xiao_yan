from fastapi.testclient import TestClient

import app.api.tools_routes as tools_routes
from app.api.capabilities_routes import _reset_capability_queue_for_tests
from app.main import app
from app.runtime_ext.runtime_config import get_runtime_config


def test_tools_execute_without_executor_heartbeat_uses_core_runner_directly():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    response = client.post("/tools/execute", json={"command": "echo hello"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "hello" in payload["output"]

    status = client.get("/capabilities/queue/status")
    assert status.status_code == 200
    assert status.json()["completed"] == 0


def test_tools_execute_with_executor_heartbeat_dispatches_then_fallbacks():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    heartbeat = client.post("/capabilities/heartbeat?executor=desktop")
    assert heartbeat.status_code == 200

    response = client.post("/tools/execute", json={"command": "echo hello"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "hello" in payload["output"]

    status = client.get("/capabilities/queue/status")
    assert status.status_code == 200
    # shell.run currently has no desktop executor implementation, so this
    # path dispatches first and then times out to core fallback.
    assert status.json()["completed"] == 1


def test_tools_execute_blocked_command_is_rejected_before_dispatch():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    heartbeat = client.post("/capabilities/heartbeat?executor=desktop")
    assert heartbeat.status_code == 200

    response = client.post("/tools/execute", json={"command": "rm -rf /"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["exit_code"] == -1

    status = client.get("/capabilities/queue/status")
    assert status.status_code == 200
    # blocked command should fail fast and never enter capability queue.
    assert status.json()["completed"] == 0


def test_tools_execute_dispatch_uses_runtime_shell_policy(monkeypatch):
    _reset_capability_queue_for_tests()
    client = TestClient(app)
    config = get_runtime_config()
    snapshot = config.get_capability_shell_policy()
    captured: dict[str, object] = {}

    def fake_dispatch_and_wait(payload, *, timeout_seconds: float = 1.0, poll_interval_seconds: float = 0.05):
        _ = timeout_seconds
        _ = poll_interval_seconds
        captured["payload"] = payload
        return None

    monkeypatch.setattr(tools_routes, "dispatch_and_wait", fake_dispatch_and_wait)

    try:
        config.update_capability_shell_policy(
            allowed_executables=["echo", "git"],
            allowed_git_subcommands=["status"],
            source="test_case",
        )
        heartbeat = client.post("/capabilities/heartbeat?executor=desktop")
        assert heartbeat.status_code == 200

        response = client.post("/tools/execute", json={"command": "echo hello"})
        assert response.status_code == 200
        assert response.json()["success"] is True

        payload = captured["payload"]
        assert payload.args["allowed_executables"] == ["echo", "git"]
        assert payload.args["allowed_git_subcommands"] == ["status"]
        assert payload.args["policy_version"] == snapshot["version"]
        assert payload.args["policy_revision"] == config.capability_shell_policy_revision
    finally:
        config.update_capability_shell_policy(
            allowed_executables=list(snapshot["allowed_executables"]),
            allowed_git_subcommands=list(snapshot["allowed_git_subcommands"]),
            source="test_restore",
        )
