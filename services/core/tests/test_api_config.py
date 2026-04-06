from fastapi.testclient import TestClient
import httpx

import app.api.config_routes as config_routes
from app.config import LLMProviderConfig
from app.main import app
from app.runtime_ext.runtime_config import get_runtime_config


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

    try:
        config.chat_context_limit = 7
        config.chat_provider = "minimaxi"
        config.chat_model = "gpt-5.4-mini"
        client = TestClient(app)
        response = client.get("/config")
        assert response.status_code == 200
        assert response.json() == {
            "chat_context_limit": 7,
            "chat_provider": "minimaxi",
            "chat_model": "gpt-5.4-mini",
        }
    finally:
        config.chat_context_limit = original_limit
        config.chat_provider = original_provider
        config.chat_model = original_model


def test_update_config_supports_provider_and_model_patch(monkeypatch):
    config = get_runtime_config()
    original_limit = config.chat_context_limit
    original_provider = config.chat_provider
    original_model = config.chat_model

    monkeypatch.setattr(config_routes, "get_llm_provider_configs", _provider_catalog)

    try:
        config.chat_context_limit = 6
        config.chat_provider = "openai"
        config.chat_model = "gpt-5.4"

        client = TestClient(app)
        response = client.put(
            "/config",
            json={"chat_provider": "minimaxi", "chat_model": "MiniMax-M2.7"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "chat_context_limit": 6,
            "chat_provider": "minimaxi",
            "chat_model": "MiniMax-M2.7",
        }
    finally:
        config.chat_context_limit = original_limit
        config.chat_provider = original_provider
        config.chat_model = original_model


def test_update_config_rejects_empty_patch():
    client = TestClient(app)
    response = client.put("/config", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "at least one config field is required"


def test_update_config_switch_provider_without_model_uses_provider_default(monkeypatch):
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model

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
        }
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model


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
