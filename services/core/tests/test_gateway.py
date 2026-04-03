from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage


def test_gateway_normalizes_messages():
    gateway = ChatGateway(api_key="test-key", model="gpt-5.4")
    payload = gateway.build_payload([ChatMessage(role="user", content="hi")])
    assert payload["model"] == "gpt-5.4"
    assert payload["messages"][0]["content"] == "hi"
