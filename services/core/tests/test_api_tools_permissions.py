import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import app.api.tool_capability_bridge as tool_capability_bridge
from app.main import app
from app.runtime_ext.runtime_config import get_runtime_config


def test_tools_read_file_uses_chat_folder_permissions():
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir).resolve()
            target = folder / "external.txt"
            target.write_text("external content", encoding="utf-8")

            client = TestClient(app)

            denied = client.get("/tools/files/read", params={"path": str(target)})
            assert denied.status_code == 200
            assert "error" in denied.json()

            config.set_folder_permission(str(folder), "read_only")

            allowed = client.get("/tools/files/read", params={"path": str(target)})
            assert allowed.status_code == 200
            assert "error" not in allowed.json()
            assert allowed.json()["path"] == str(target)
            assert allowed.json()["line_count"] == 1
    finally:
        config.clear_folder_permissions()


def test_tools_search_file_uses_chat_folder_permissions():
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir).resolve()
            target = folder / "external.py"
            target.write_text("print('hello')\n# TODO: capability search\n", encoding="utf-8")

            client = TestClient(app)

            denied = client.get(
                "/tools/files/search",
                params={"query": "TODO", "search_path": str(folder), "file_pattern": "*.py", "max_results": 20},
            )
            assert denied.status_code == 200
            assert "error" in denied.json()

            config.set_folder_permission(str(folder), "read_only")

            allowed = client.get(
                "/tools/files/search",
                params={"query": "TODO", "search_path": str(folder), "file_pattern": "*.py", "max_results": 20},
            )
            assert allowed.status_code == 200
            payload = allowed.json()
            assert "error" not in payload
            assert payload["total_matches"] >= 1
    finally:
        config.clear_folder_permissions()


def test_tools_file_dispatch_uses_runtime_file_policy(monkeypatch):
    config = get_runtime_config()
    config.clear_folder_permissions()
    policy_snapshot = config.get_capability_file_policy()
    captured: dict[str, object] = {}

    def fake_dispatch_and_wait(payload, *, timeout_seconds: float = 1.0, poll_interval_seconds: float = 0.05):
        _ = timeout_seconds
        _ = poll_interval_seconds
        captured["payload"] = payload
        return None

    monkeypatch.setattr(tool_capability_bridge, "dispatch_and_wait", fake_dispatch_and_wait)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir).resolve()
            target = folder / "external.txt"
            target.write_text("external content", encoding="utf-8")
            config.set_folder_permission(str(folder), "read_only")
            config.update_capability_file_policy(
                max_read_bytes=4096,
                max_write_bytes=4096,
                max_search_results=10,
                max_list_entries=20,
                allowed_search_file_patterns=["*.py", "*.md"],
                source="test_case",
            )

            client = TestClient(app)
            heartbeat = client.post("/capabilities/heartbeat?executor=desktop")
            assert heartbeat.status_code == 200

            response = client.get("/tools/files/read", params={"path": str(target), "max_bytes": 1024})
            assert response.status_code == 200
            assert "error" not in response.json()

            payload = captured["payload"]
            file_policy = payload.args["file_policy"]
            assert file_policy["max_read_bytes"] == 4096
            assert file_policy["max_write_bytes"] == 4096
            assert file_policy["max_search_results"] == 10
            assert file_policy["max_list_entries"] == 20
            assert file_policy["allowed_search_file_patterns"] == ["*.py", "*.md"]
            assert file_policy["revision"] == config.capability_file_policy_revision
    finally:
        config.clear_folder_permissions()
        config.update_capability_file_policy(
            max_read_bytes=int(policy_snapshot["max_read_bytes"]),
            max_write_bytes=int(policy_snapshot["max_write_bytes"]),
            max_search_results=int(policy_snapshot["max_search_results"]),
            max_list_entries=int(policy_snapshot["max_list_entries"]),
            allowed_search_file_patterns=list(policy_snapshot["allowed_search_file_patterns"]),
            source="test_restore",
        )
