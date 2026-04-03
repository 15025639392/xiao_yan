import os

import httpx

from app.config import load_local_env
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

    def close(self) -> None:
        self._http_client.close()


GatewayResponse = ChatResult


def _extract_output_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]

    for item in data.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") not in {"output_text", "text"}:
                continue

            text = content.get("text")
            if text:
                return text

    raise ValueError("response payload did not contain output text")
