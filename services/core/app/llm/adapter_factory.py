from __future__ import annotations

from app.llm.deepseek_chat_completions_adapter import DeepSeekChatCompletionsWireAdapter
from app.llm.generic_chat_completions_adapter import GenericChatCompletionsWireAdapter
from app.llm.minimax_chat_completions_adapter import MiniMaxChatCompletionsWireAdapter
from app.llm.openai_chat_completions_adapter import OpenAIChatCompletionsWireAdapter
from app.llm.generic_responses_adapter import GenericResponsesWireAdapter
from app.llm.openai_responses_adapter import OpenAIResponsesWireAdapter
from app.llm.wire_adapter_types import ChatWireAdapter


def get_wire_adapter(provider_id: str, wire_api: str) -> ChatWireAdapter:
    normalized_provider = (provider_id or "").strip().lower()
    if normalized_provider == "openai":
        if wire_api == "responses":
            return OpenAIResponsesWireAdapter()
        if wire_api == "chat":
            return OpenAIChatCompletionsWireAdapter()
    if normalized_provider == "minimaxi" and wire_api == "chat":
        return MiniMaxChatCompletionsWireAdapter()
    if normalized_provider == "deepseek" and wire_api == "chat":
        return DeepSeekChatCompletionsWireAdapter()
    if wire_api == "responses":
        return GenericResponsesWireAdapter()
    if wire_api == "chat":
        return GenericChatCompletionsWireAdapter()
    raise ValueError(f"unsupported wire_api: {wire_api}")
