from app.llm.schemas import ChatMessage


class ChatGateway:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def build_payload(self, messages: list[ChatMessage]) -> dict:
        return {
            "model": self.model,
            "messages": [message.model_dump() for message in messages],
        }
