from fastapi.testclient import TestClient
import httpx
from types import SimpleNamespace

import app.api.config_routes as config_routes
from app.config import LLMProviderConfig
from app.main import app
from app.runtime_ext.runtime_config import get_runtime_config


def _goal_admission_snapshot() -> dict[str, float]:
    config = get_runtime_config()
    return {
        "stability_warning_rate": config.goal_admission_stability_warning_rate,
        "stability_danger_rate": config.goal_admission_stability_danger_rate,
        "user_topic_min_score": float(getattr(config, "goal_admission_user_topic_min_score", 0.68)),
        "user_topic_defer_score": float(getattr(config, "goal_admission_user_topic_defer_score", 0.45)),
        "world_event_min_score": float(getattr(config, "goal_admission_world_event_min_score", 0.75)),
        "world_event_defer_score": float(getattr(config, "goal_admission_world_event_defer_score", 0.52)),
        "chain_next_min_score": float(getattr(config, "goal_admission_chain_next_min_score", 0.62)),
        "chain_next_defer_score": float(getattr(config, "goal_admission_chain_next_defer_score", 0.45)),
    }


def _restore_goal_admission_snapshot(snapshot: dict[str, float]) -> None:
    config = get_runtime_config()
    config.goal_admission_stability_warning_rate = snapshot["stability_warning_rate"]
    config.goal_admission_stability_danger_rate = snapshot["stability_danger_rate"]

    optional_config_attrs = {
        "goal_admission_user_topic_min_score": snapshot["user_topic_min_score"],
        "goal_admission_user_topic_defer_score": snapshot["user_topic_defer_score"],
        "goal_admission_world_event_min_score": snapshot["world_event_min_score"],
        "goal_admission_world_event_defer_score": snapshot["world_event_defer_score"],
        "goal_admission_chain_next_min_score": snapshot["chain_next_min_score"],
        "goal_admission_chain_next_defer_score": snapshot["chain_next_defer_score"],
    }
    for attr, value in optional_config_attrs.items():
        if hasattr(config, attr):
            setattr(config, attr, value)

    service = getattr(app.state, "goal_admission_service", None)
    if service is not None:
        service.min_score = snapshot["user_topic_min_score"]
        service.defer_score = snapshot["user_topic_defer_score"]
        service.world_min_score = snapshot["world_event_min_score"]
        service.world_defer_score = snapshot["world_event_defer_score"]
        service.chain_min_score = snapshot["chain_next_min_score"]
        service.chain_defer_score = snapshot["chain_next_defer_score"]


def _capability_policy_snapshot() -> dict[str, dict]:
    config = get_runtime_config()
    return {
        "shell": config.get_capability_shell_policy(),
        "file": config.get_capability_file_policy(),
    }


def _restore_capability_policy_snapshot(snapshot: dict[str, dict]) -> None:
    config = get_runtime_config()
    shell = snapshot["shell"]
    file_policy = snapshot["file"]
    config.update_capability_shell_policy(
        allowed_executables=list(shell["allowed_executables"]),
        allowed_git_subcommands=list(shell["allowed_git_subcommands"]),
        source="test_restore",
    )
    config.update_capability_file_policy(
        max_read_bytes=int(file_policy["max_read_bytes"]),
        max_write_bytes=int(file_policy["max_write_bytes"]),
        max_search_results=int(file_policy["max_search_results"]),
        max_list_entries=int(file_policy["max_list_entries"]),
        allowed_search_file_patterns=list(file_policy["allowed_search_file_patterns"]),
        source="test_restore",
    )


def _provider_catalog() -> list[LLMProviderConfig]:
    return [
        LLMProviderConfig(
            provider_id="openai",
            provider_name="OpenAI",
            api_key="openai-key",
            base_url="https://api.openai.com/v1",
            wire_api="responses",
            default_model="gpt-5.4",
        ),
        LLMProviderConfig(
            provider_id="minimaxi",
            provider_name="MiniMax",
            api_key="minimax-key",
            base_url="https://api.minimaxi.com/v1",
            wire_api="chat",
            default_model="MiniMax-M2.7",
        ),
    ]


def test_get_config_returns_context_limit_provider_and_chat_model():
    config = get_runtime_config()
    original_limit = config.chat_context_limit
    original_provider = config.chat_provider
    original_model = config.chat_model
    original_timeout = config.chat_read_timeout_seconds

    try:
        config.chat_context_limit = 7
        config.chat_provider = "minimaxi"
        config.chat_model = "gpt-5.4-mini"
        config.chat_read_timeout_seconds = 240
        client = TestClient(app)
        response = client.get("/config")
        assert response.status_code == 200
        assert response.json() == {
            "chat_context_limit": 7,
            "chat_provider": "minimaxi",
            "chat_model": "gpt-5.4-mini",
            "chat_read_timeout_seconds": 240,
        }
    finally:
        config.chat_context_limit = original_limit
        config.chat_provider = original_provider
        config.chat_model = original_model
        config.chat_read_timeout_seconds = original_timeout


def test_update_config_supports_provider_and_model_patch(monkeypatch):
    config = get_runtime_config()
    original_limit = config.chat_context_limit
    original_provider = config.chat_provider
    original_model = config.chat_model
    original_timeout = config.chat_read_timeout_seconds

    monkeypatch.setattr(config_routes, "get_llm_provider_configs", _provider_catalog)

    try:
        config.chat_context_limit = 6
        config.chat_provider = "openai"
        config.chat_model = "gpt-5.4"

        client = TestClient(app)
        response = client.put(
            "/config",
            json={"chat_provider": "minimaxi", "chat_model": "MiniMax-M2.7", "chat_read_timeout_seconds": 200},
        )
        assert response.status_code == 200
        assert response.json() == {
            "chat_context_limit": 6,
            "chat_provider": "minimaxi",
            "chat_model": "MiniMax-M2.7",
            "chat_read_timeout_seconds": 200,
        }
    finally:
        config.chat_context_limit = original_limit
        config.chat_provider = original_provider
        config.chat_model = original_model
        config.chat_read_timeout_seconds = original_timeout


def test_update_config_rejects_empty_patch():
    client = TestClient(app)
    response = client.put("/config", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "at least one config field is required"


def test_update_config_switch_provider_without_model_uses_provider_default(monkeypatch):
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model
    original_timeout = config.chat_read_timeout_seconds

    monkeypatch.setattr(config_routes, "get_llm_provider_configs", _provider_catalog)

    try:
        config.chat_provider = "openai"
        config.chat_model = "gpt-5.4"
        client = TestClient(app)
        response = client.put("/config", json={"chat_provider": "minimaxi"})
        assert response.status_code == 200
        assert response.json() == {
            "chat_context_limit": config.chat_context_limit,
            "chat_provider": "minimaxi",
            "chat_model": "MiniMax-M2.7",
            "chat_read_timeout_seconds": config.chat_read_timeout_seconds,
        }
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model
        config.chat_read_timeout_seconds = original_timeout


def test_get_chat_models_returns_multi_provider_catalog_and_partial_errors(monkeypatch):
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model

    monkeypatch.setattr(config_routes, "get_llm_provider_configs", _provider_catalog)

    class StubGateway:
        def __init__(self, api_key: str, model: str, base_url: str, wire_api: str) -> None:
            self.base_url = base_url
            self.model = model

        def list_models(self) -> list[str]:
            if "minimaxi.com" in self.base_url:
                raise RuntimeError("upstream 502")
            return ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]

        def close(self) -> None:
            return None

    def stub_from_provider_config(provider_config: LLMProviderConfig, *, model: str | None = None):
        return StubGateway(
            api_key=provider_config.api_key,
            model=model or provider_config.default_model,
            base_url=provider_config.base_url,
            wire_api=provider_config.wire_api,
        )

    monkeypatch.setattr(config_routes.ChatGateway, "from_provider_config", staticmethod(stub_from_provider_config))

    try:
        config.chat_provider = "minimaxi"
        config.chat_model = "MiniMax-M2.7"
        client = TestClient(app)
        response = client.get("/config/chat-models")
        assert response.status_code == 200
        assert response.json() == {
            "providers": [
                {
                    "provider_id": "openai",
                    "provider_name": "OpenAI",
                    "models": ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"],
                    "default_model": "gpt-5.4",
                    "error": None,
                },
                {
                    "provider_id": "minimaxi",
                    "provider_name": "MiniMax",
                    "models": ["MiniMax-M2.7"],
                    "default_model": "MiniMax-M2.7",
                    "error": "upstream 502",
                },
            ],
            "current_provider": "minimaxi",
            "current_model": "MiniMax-M2.7",
        }
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model


def test_get_chat_models_minimaxi_404_falls_back_without_error(monkeypatch):
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model

    monkeypatch.setattr(config_routes, "get_llm_provider_configs", _provider_catalog)

    class StubGateway:
        def __init__(self, api_key: str, model: str, base_url: str, wire_api: str) -> None:
            self.base_url = base_url

        def list_models(self) -> list[str]:
            if "minimaxi.com" in self.base_url:
                request = httpx.Request("GET", "https://api.minimaxi.com/v1/models")
                response = httpx.Response(404, request=request, text="404 Page not found")
                raise httpx.HTTPStatusError("404", request=request, response=response)
            return ["gpt-5.4", "gpt-5.4-mini"]

        def close(self) -> None:
            return None

    def stub_from_provider_config(provider_config: LLMProviderConfig, *, model: str | None = None):
        return StubGateway(
            api_key=provider_config.api_key,
            model=model or provider_config.default_model,
            base_url=provider_config.base_url,
            wire_api=provider_config.wire_api,
        )

    monkeypatch.setattr(config_routes.ChatGateway, "from_provider_config", staticmethod(stub_from_provider_config))

    try:
        config.chat_provider = "minimaxi"
        config.chat_model = "MiniMax-M2.7"
        client = TestClient(app)
        response = client.get("/config/chat-models")
        assert response.status_code == 200
        body = response.json()
        minimaxi = next(item for item in body["providers"] if item["provider_id"] == "minimaxi")
        assert minimaxi["error"] is None
        assert "MiniMax-M2.7" in minimaxi["models"]
        assert "MiniMax-M2.7-highspeed" in minimaxi["models"]
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model


def test_get_self_programming_config_returns_defaults():
    client = TestClient(app)
    response = client.get("/config/self-programming")
    assert response.status_code == 200
    assert response.json() == {
        "hard_failure_cooldown_minutes": 60,
        "proactive_cooldown_minutes": 720,
    }


def test_update_self_programming_config_supports_patch():
    client = TestClient(app)
    response = client.put(
        "/config/self-programming",
        json={
            "hard_failure_cooldown_minutes": 45,
            "proactive_cooldown_minutes": 360,
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "hard_failure_cooldown_minutes": 45,
        "proactive_cooldown_minutes": 360,
    }

    # 恢复默认值，避免污染后续测试
    restore = client.put(
        "/config/self-programming",
        json={
            "hard_failure_cooldown_minutes": 60,
            "proactive_cooldown_minutes": 720,
        },
    )
    assert restore.status_code == 200


def test_update_self_programming_config_rejects_empty_patch():
    client = TestClient(app)
    response = client.put("/config/self-programming", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "at least one self-programming config field is required"


def test_get_goal_admission_config_returns_full_threshold_payload():
    snapshot = _goal_admission_snapshot()
    client = TestClient(app)
    expected = {
        "stability_warning_rate": 0.61,
        "stability_danger_rate": 0.34,
        "user_topic_min_score": 0.69,
        "user_topic_defer_score": 0.44,
        "world_event_min_score": 0.76,
        "world_event_defer_score": 0.51,
        "chain_next_min_score": 0.63,
        "chain_next_defer_score": 0.43,
    }
    try:
        update = client.put("/config/goal-admission", json=expected)
        assert update.status_code == 200
        response = client.get("/config/goal-admission")
        assert response.status_code == 200
        assert response.json() == expected
    finally:
        _restore_goal_admission_snapshot(snapshot)


def test_update_goal_admission_config_supports_source_threshold_patch_and_applies_to_stats():
    snapshot = _goal_admission_snapshot()
    client = TestClient(app)
    try:
        baseline = client.put(
            "/config/goal-admission",
            json={
                "stability_warning_rate": 0.6,
                "stability_danger_rate": 0.35,
                "user_topic_min_score": 0.68,
                "user_topic_defer_score": 0.45,
                "world_event_min_score": 0.75,
                "world_event_defer_score": 0.52,
                "chain_next_min_score": 0.62,
                "chain_next_defer_score": 0.45,
            },
        )
        assert baseline.status_code == 200

        response = client.put(
            "/config/goal-admission",
            json={
                "stability_warning_rate": 0.7,
                "stability_danger_rate": 0.4,
                "user_topic_min_score": 0.71,
                "user_topic_defer_score": 0.49,
                "chain_next_min_score": 0.66,
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "stability_warning_rate": 0.7,
            "stability_danger_rate": 0.4,
            "user_topic_min_score": 0.71,
            "user_topic_defer_score": 0.49,
            "world_event_min_score": 0.75,
            "world_event_defer_score": 0.52,
            "chain_next_min_score": 0.66,
            "chain_next_defer_score": 0.45,
        }

        stats_response = client.get("/goals/admission/stats")
        assert stats_response.status_code == 200
        stats_payload = stats_response.json()
        assert stats_payload["thresholds"] == {
            "user_topic": {"min_score": 0.71, "defer_score": 0.49},
            "world_event": {"min_score": 0.75, "defer_score": 0.52},
            "chain_next": {"min_score": 0.66, "defer_score": 0.45},
        }
    finally:
        _restore_goal_admission_snapshot(snapshot)


def test_update_goal_admission_config_rejects_invalid_threshold_order():
    client = TestClient(app)
    response = client.put(
        "/config/goal-admission",
        json={
            "stability_warning_rate": 0.3,
            "stability_danger_rate": 0.5,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "stability_danger_rate must be <= stability_warning_rate"


def test_update_goal_admission_config_rejects_invalid_source_threshold_order():
    client = TestClient(app)
    response = client.put(
        "/config/goal-admission",
        json={
            "world_event_min_score": 0.5,
            "world_event_defer_score": 0.7,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "world_event_defer_score must be <= world_event_min_score"


def test_update_goal_admission_config_rejects_empty_patch():
    client = TestClient(app)
    response = client.put("/config/goal-admission", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "at least one goal-admission config field is required"


def test_goal_admission_config_history_returns_recent_entries():
    snapshot = _goal_admission_snapshot()
    client = TestClient(app)
    try:
        update_response = client.put(
            "/config/goal-admission",
            json={
                "stability_warning_rate": 0.72,
                "stability_danger_rate": 0.41,
                "user_topic_min_score": 0.7,
                "user_topic_defer_score": 0.48,
            },
        )
        assert update_response.status_code == 200

        history_response = client.get("/config/goal-admission/history?limit=2")
        assert history_response.status_code == 200
        payload = history_response.json()
        assert len(payload["items"]) >= 1
        latest = payload["items"][0]
        assert latest["source"] == "api_update"
        assert latest["stability_warning_rate"] == 0.72
        assert latest["stability_danger_rate"] == 0.41
        assert latest["user_topic_min_score"] == 0.7
        assert latest["user_topic_defer_score"] == 0.48
        assert latest["revision"] >= 1
    finally:
        _restore_goal_admission_snapshot(snapshot)


def test_rollback_goal_admission_config_returns_previous_revision():
    snapshot = _goal_admission_snapshot()
    client = TestClient(app)
    try:
        baseline = client.put(
            "/config/goal-admission",
            json={
                "stability_warning_rate": 0.66,
                "stability_danger_rate": 0.33,
                "chain_next_min_score": 0.61,
                "chain_next_defer_score": 0.42,
            },
        )
        assert baseline.status_code == 200

        changed = client.put(
            "/config/goal-admission",
            json={
                "stability_warning_rate": 0.74,
                "stability_danger_rate": 0.4,
                "chain_next_min_score": 0.67,
                "chain_next_defer_score": 0.46,
            },
        )
        assert changed.status_code == 200

        rollback = client.post("/config/goal-admission/rollback")
        assert rollback.status_code == 200
        rollback_payload = rollback.json()
        assert rollback_payload["stability_warning_rate"] == 0.66
        assert rollback_payload["stability_danger_rate"] == 0.33
        assert rollback_payload["chain_next_min_score"] == 0.61
        assert rollback_payload["chain_next_defer_score"] == 0.42
        assert rollback_payload["rolled_back_from_revision"] >= 1
        assert rollback_payload["revision"] > rollback_payload["rolled_back_from_revision"]

        config_response = client.get("/config/goal-admission")
        assert config_response.status_code == 200
        assert config_response.json() == {
            "stability_warning_rate": 0.66,
            "stability_danger_rate": 0.33,
            "user_topic_min_score": snapshot["user_topic_min_score"],
            "user_topic_defer_score": snapshot["user_topic_defer_score"],
            "world_event_min_score": snapshot["world_event_min_score"],
            "world_event_defer_score": snapshot["world_event_defer_score"],
            "chain_next_min_score": 0.61,
            "chain_next_defer_score": 0.42,
        }
    finally:
        _restore_goal_admission_snapshot(snapshot)


def test_get_and_update_capability_shell_policy_config_with_history():
    snapshot = _capability_policy_snapshot()
    client = TestClient(app)
    try:
        response = client.get("/config/capabilities/shell-policy")
        assert response.status_code == 200
        baseline = response.json()
        assert isinstance(baseline["version"], str)
        assert baseline["revision"] >= 1

        update = client.put(
            "/config/capabilities/shell-policy",
            json={
                "allowed_executables": ["echo", "git"],
                "allowed_git_subcommands": ["status"],
            },
        )
        assert update.status_code == 200
        updated = update.json()
        assert updated["allowed_executables"] == ["echo", "git"]
        assert updated["allowed_git_subcommands"] == ["status"]
        assert updated["revision"] >= baseline["revision"]

        history = client.get("/config/capabilities/shell-policy/history?limit=2")
        assert history.status_code == 200
        payload = history.json()
        assert len(payload["items"]) >= 1
        latest = payload["items"][0]
        assert latest["source"] == "api_update"
        assert latest["allowed_executables"] == ["echo", "git"]
        assert latest["allowed_git_subcommands"] == ["status"]
    finally:
        _restore_capability_policy_snapshot(snapshot)


def test_update_capability_shell_policy_rejects_unsupported_executable():
    client = TestClient(app)
    response = client.put(
        "/config/capabilities/shell-policy",
        json={
            "allowed_executables": ["echo", "curl"],
            "allowed_git_subcommands": ["status"],
        },
    )
    assert response.status_code == 400
    assert "unsupported value" in response.json()["detail"]


def test_get_and_update_capability_file_policy_config_with_history():
    snapshot = _capability_policy_snapshot()
    client = TestClient(app)
    try:
        baseline = client.get("/config/capabilities/file-policy")
        assert baseline.status_code == 200
        baseline_payload = baseline.json()
        assert baseline_payload["revision"] >= 1

        next_max_read = 4096 if baseline_payload["max_read_bytes"] != 4096 else 8192
        update = client.put(
            "/config/capabilities/file-policy",
            json={
                "max_read_bytes": next_max_read,
                "max_write_bytes": 4096,
                "max_search_results": 10,
                "max_list_entries": 20,
                "allowed_search_file_patterns": ["*.py", "*.md"],
            },
        )
        assert update.status_code == 200
        updated = update.json()
        assert updated["max_read_bytes"] == next_max_read
        assert updated["max_write_bytes"] == 4096
        assert updated["max_search_results"] == 10
        assert updated["max_list_entries"] == 20
        assert updated["allowed_search_file_patterns"] == ["*.py", "*.md"]

        history = client.get("/config/capabilities/file-policy/history?limit=2")
        assert history.status_code == 200
        payload = history.json()
        assert len(payload["items"]) >= 1
        latest = payload["items"][0]
        assert latest["source"] == "api_update"
        assert latest["max_read_bytes"] == next_max_read
        assert latest["allowed_search_file_patterns"] == ["*.py", "*.md"]
    finally:
        _restore_capability_policy_snapshot(snapshot)


def test_update_capability_file_policy_rejects_empty_patch():
    client = TestClient(app)
    response = client.put("/config/capabilities/file-policy", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "at least one file-policy field is required"


def test_get_data_environment_returns_snapshot(monkeypatch):
    monkeypatch.setattr(
        config_routes,
        "get_data_environment_snapshot",
        lambda: SimpleNamespace(
            testing_mode=False,
            mempalace_palace_path="/tmp/palace-default",
            mempalace_wing="wing_xiaoyan",
            mempalace_room="chat_exchange",
            default_backup_directory="/tmp/backups",
        ),
    )

    client = TestClient(app)
    response = client.get("/config/data-environment")
    assert response.status_code == 200
    assert response.json() == {
        "testing_mode": False,
        "mempalace_palace_path": "/tmp/palace-default",
        "mempalace_wing": "wing_xiaoyan",
        "mempalace_room": "chat_exchange",
        "default_backup_directory": "/tmp/backups",
        "switch_backup_path": None,
    }


def test_update_data_environment_switches_mode_with_auto_backup(monkeypatch):
    calls: dict[str, object] = {"testing_mode": False}

    def stub_snapshot():
        return SimpleNamespace(
            testing_mode=bool(calls["testing_mode"]),
            mempalace_palace_path="/tmp/palace-testing" if calls["testing_mode"] else "/tmp/palace-default",
            mempalace_wing="wing_xiaoyan",
            mempalace_room="chat_exchange_testing" if calls["testing_mode"] else "chat_exchange",
            default_backup_directory="/tmp/backups",
        )

    def stub_apply(testing_mode: bool) -> None:
        calls["testing_mode"] = testing_mode

    monkeypatch.setattr(config_routes, "get_data_environment_snapshot", stub_snapshot)
    monkeypatch.setattr(config_routes, "is_testing_data_mode_enabled", lambda: False)
    monkeypatch.setattr(
        config_routes,
        "create_data_backup_archive",
        lambda *_args, **_kwargs: SimpleNamespace(
            backup_path="/tmp/backups/switch.zip",
            created_at="2026-04-12T00:00:00+00:00",
            restored_keys=["state"],
        ),
    )
    monkeypatch.setattr(config_routes, "apply_testing_data_mode", stub_apply)
    monkeypatch.setattr(config_routes, "reload_runtime", lambda _app: calls.update({"reloaded": True}))

    client = TestClient(app)
    response = client.put("/config/data-environment", json={"testing_mode": True, "backup_before_switch": True})
    assert response.status_code == 200
    assert response.json() == {
        "testing_mode": True,
        "mempalace_palace_path": "/tmp/palace-testing",
        "mempalace_wing": "wing_xiaoyan",
        "mempalace_room": "chat_exchange_testing",
        "default_backup_directory": "/tmp/backups",
        "switch_backup_path": "/tmp/backups/switch.zip",
    }
    assert calls["testing_mode"] is True
    assert calls.get("reloaded") is True


def test_import_data_backup_endpoint_creates_safety_backup_and_reloads(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        config_routes,
        "create_data_backup_archive",
        lambda *_args, **_kwargs: SimpleNamespace(
            backup_path="/tmp/backups/pre-import.zip",
            created_at="2026-04-12T00:00:00+00:00",
            restored_keys=["state"],
        ),
    )
    monkeypatch.setattr(
        config_routes,
        "import_data_backup_archive",
        lambda path: ["state", "goals"] if path == "/tmp/backups/source.zip" else [],
    )
    monkeypatch.setattr(config_routes, "reload_runtime", lambda _app: calls.update({"reloaded": True}))

    client = TestClient(app)
    response = client.post(
        "/config/data-backup/import",
        json={"backup_path": "/tmp/backups/source.zip", "make_pre_import_backup": True},
    )
    assert response.status_code == 200
    assert response.json() == {
        "imported_from": "/tmp/backups/source.zip",
        "restored_keys": ["state", "goals"],
        "pre_import_backup_path": "/tmp/backups/pre-import.zip",
    }
    assert calls.get("reloaded") is True
