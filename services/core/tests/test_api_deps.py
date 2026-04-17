import httpx

import app.api.deps as deps
from app.config import LLMProviderConfig
from app.runtime_ext.runtime_config import get_runtime_config


def test_get_chat_gateway_uses_runtime_read_timeout(monkeypatch):
    runtime_config = get_runtime_config()
    original_timeout = runtime_config.chat_read_timeout_seconds
    captured: dict[str, object] = {}

    provider = LLMProviderConfig(
        provider_id="openai",
        provider_name="OpenAI",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        wire_api="responses",
        default_model="gpt-5.4",
    )

    class StubGateway:
        def __init__(self, http_client: httpx.Client) -> None:
            self.http_client = http_client

        def close(self) -> None:
            self.http_client.close()

    def fake_from_provider_config(provider_config, *, model=None, http_client=None):
        _ = (provider_config, model)
        assert isinstance(http_client, httpx.Client)
        captured["timeout"] = http_client.timeout
        return StubGateway(http_client)

    monkeypatch.setattr(deps, "get_llm_provider_configs", lambda: [provider])
    monkeypatch.setattr(deps.ChatGateway, "from_provider_config", staticmethod(fake_from_provider_config))

    runtime_config.chat_read_timeout_seconds = 245
    try:
        generator = deps.get_chat_gateway()
        gateway = next(generator)
        assert gateway is not None
        timeout = captured["timeout"]
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.read == 245
        assert timeout.connect == 10.0
        try:
            next(generator)
        except StopIteration:
            pass
        else:
            raise AssertionError("expected generator to finish")
    finally:
        runtime_config.chat_read_timeout_seconds = original_timeout
