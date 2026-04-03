from fastapi.testclient import TestClient

from app.llm.schemas import ChatMessage
from app.llm.gateway import GatewayResponse
from app.main import app, get_chat_gateway, get_memory_repository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


class StubGateway:
    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []

    def create_response(self, messages, instructions=None) -> GatewayResponse:
        self.last_messages = list(messages)
        return GatewayResponse(
            response_id="resp_test",
            output_text=f"echo:{messages[-1].content}",
        )

    def close(self) -> None:
        return None


def test_post_chat_returns_gateway_response():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_test",
            "output_text": "echo:hello",
        }
        recent = memory_repository.list_recent(limit=5)
        assert [event.role for event in reversed(recent)] == ["user", "assistant"]
        assert [event.content for event in reversed(recent)] == ["hello", "echo:hello"]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_recent_memory_in_gateway_messages():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="user", content="昨天我们聊了星星")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="我记得你喜欢夜空")
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "今天还记得吗"})
        assert response.status_code == 200
        assert [(message.role, message.content) for message in gateway.last_messages] == [
            ("user", "昨天我们聊了星星"),
            ("assistant", "我记得你喜欢夜空"),
            ("user", "今天还记得吗"),
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_prefers_relevant_memory_over_only_recent_memory():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="user", content="我们前天讨论过星星和银河")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="昨晚我想的是早餐和咖啡")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="user", content="今天下午整理了桌面文件")
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你还记得我们聊过的星星吗"})
        assert response.status_code == 200
        assert ("user", "我们前天讨论过星星和银河") in [
            (message.role, message.content) for message in gateway.last_messages
        ]
        assert gateway.last_messages[-1].content == "你还记得我们聊过的星星吗"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_relevant_world_event_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="world", content="夜里很安静，我有点困，但还惦记着整理今天的对话记忆。")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="我刚刚还在想着今天的整理。")
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你刚刚经历了什么"})
        assert response.status_code == 200
        assert ("system", "最近你的世界事件：夜里很安静，我有点困，但还惦记着整理今天的对话记忆。") in [
            (message.role, message.content) for message in gateway.last_messages
        ]
        assert gateway.last_messages[-1].content == "你刚刚经历了什么"
    finally:
        app.dependency_overrides.clear()


def test_get_messages_returns_recent_chat_events():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="user", content="第一句")
    )
    memory_repository.save_event(
        MemoryEvent(kind="assistant_note", role="assistant", content="内部笔记")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="第二句")
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.get("/messages")
        assert response.status_code == 200
        assert response.json() == {
            "messages": [
                {"role": "user", "content": "第一句"},
                {"role": "assistant", "content": "第二句"},
            ]
        }
    finally:
        app.dependency_overrides.clear()
