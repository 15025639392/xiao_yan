import os
import json
from collections.abc import Generator

import httpx

from app.config import load_local_env
from app.llm.gateway_events import (
    extract_error_message as _extract_error_message,
    extract_output_text as _extract_output_text,
    extract_response_id as _extract_response_id,
    iter_sse_events as _iter_sse_events,
)
from app.llm.schemas import ChatMessage, ChatResult


class ChatGateway:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.wire_api = wire_api
        self._http_client = http_client or httpx.Client(timeout=30.0)

    @classmethod
    def from_env(cls) -> "ChatGateway":
        load_local_env()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            wire_api=os.getenv("OPENAI_WIRE_API", "responses"),
        )

    def build_payload(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "input": [message.model_dump() for message in messages],
        }
        if instructions:
            payload["instructions"] = instructions
        return payload

    def create_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        if self.wire_api != "responses":
            raise ValueError(f"unsupported wire_api: {self.wire_api}")

        response = self._http_client.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=self.build_payload(messages, instructions=instructions),
        )
        response.raise_for_status()

        data = response.json()
        return ChatResult(
            response_id=data.get("id"),
            output_text=_extract_output_text(data),
        )

    def stream_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> Generator[dict[str, str | None], None, None]:
        if self.wire_api != "responses":
            raise ValueError(f"unsupported wire_api: {self.wire_api}")

        output_fragments: list[str] = []
        current_response_id: str | None = None

        with self._http_client.stream(
            "POST",
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=self.build_payload(messages, instructions=instructions) | {"stream": True},
        ) as response:
            response.raise_for_status()

            for event_name, event_data in _iter_sse_events(response.iter_lines()):
                if event_data == "[DONE]":
                    break

                payload = json.loads(event_data)

                if event_name == "response.created":
                    current_response_id = _extract_response_id(payload) or current_response_id
                    yield {
                        "type": "response_started",
                        "response_id": current_response_id,
                    }
                    continue

                if event_name == "response.output_text.delta":
                    delta = payload.get("delta") or ""
                    if delta:
                        output_fragments.append(delta)
                        yield {
                            "type": "text_delta",
                            "delta": delta,
                        }
                    continue

                if event_name == "response.completed":
                    completed_response = payload.get("response", payload)
                    current_response_id = _extract_response_id(payload) or current_response_id
                    output_text = (
                        _extract_output_text(completed_response)
                        if isinstance(completed_response, dict) and (completed_response.get("output") or completed_response.get("output_text"))
                        else "".join(output_fragments)
                    )
                    yield {
                        "type": "response_completed",
                        "response_id": current_response_id,
                        "output_text": output_text,
                    }
                    continue

                if event_name == "error":
                    error_message = _extract_error_message(payload)
                    yield {
                        "type": "response_failed",
                        "error": error_message,
                    }

    def close(self) -> None:
        self._http_client.close()


GatewayResponse = ChatResult
from app.llm.enhanced_gateway import EnhancedChatGateway
