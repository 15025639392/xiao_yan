import time
from threading import Thread

from fastapi.testclient import TestClient

from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.llm.schemas import ChatMessage
from app.llm.gateway import GatewayResponse
from app.main import (
    app,
    get_chat_gateway,
    get_goal_repository,
    get_memory_repository,
    get_memory_service,
    get_state_store,
)
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.memory.service import MemoryService
from app.runtime import StateStore


class StubGateway:
    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []
        self.last_instructions: str | None = None

    def create_response(self, messages, instructions=None) -> GatewayResponse:
        self.last_messages = list(messages)
        self.last_instructions = instructions
        return GatewayResponse(
            response_id="resp_test",
            output_text=f"echo:{messages[-1].content}",
        )

    def stream_response(self, messages, instructions=None):
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_test",
        }
        for chunk in ("echo:", messages[-1].content):
            time.sleep(0.01)
            yield {
                "type": "text_delta",
                "delta": chunk,
            }
        yield {
            "type": "response_completed",
            "response_id": "resp_test",
            "output_text": f"echo:{messages[-1].content}",
        }

    def close(self) -> None:
        return None


class ResumeStubGateway(StubGateway):
    def __init__(self) -> None:
        super().__init__()
        self.stream_call_count = 0

    def stream_response(self, messages, instructions=None):
        self.last_messages = list(messages)
        self.last_instructions = instructions
        self.stream_call_count += 1
        yield {
            "type": "response_started",
            "response_id": "resp_resume",
        }
        yield {
            "type": "text_delta",
            "delta": "继续的一半",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_resume",
            "output_text": "继续的一半",
        }


class CompletionWinsStubGateway(StubGateway):
    def stream_response(self, messages, instructions=None):
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_completion_wins",
        }
        yield {
            "type": "text_delta",
            "delta": "你好呀，我是小晏。很高兴见到～\n\n今天想聊点什么？",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_completion_wins",
            "output_text": "你好呀，我是小晏。很高兴见到你～\n\n今天想聊点什么？",
        }


def test_post_chat_returns_submission_confirmation():
    memory_repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=memory_repository)
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["response_id"] == "resp_test"
        assert response.json()["assistant_message_id"].startswith("assistant_")
        recent = memory_repository.list_recent(limit=5)
        assert [event.role for event in reversed(recent)] == ["user", "assistant"]
        assert [event.content for event in reversed(recent)] == ["hello", "echo:hello"]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_uses_response_completed_output_text_as_final_content():
    memory_repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=memory_repository)
    gateway = CompletionWinsStubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你好"})
        assert response.status_code == 200
        recent = list(reversed(memory_repository.list_recent(limit=5)))
        assert [event.role for event in recent] == ["user", "assistant"]
        assert recent[1].content == "你好呀，我是小晏。很高兴见到你～\n\n今天想聊点什么？"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_streams_reply_over_realtime_socket():
    memory_repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=memory_repository)
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/app") as websocket:
            assert websocket.receive_json()["type"] == "snapshot"

            response_box: dict[str, object] = {}

            def receive_until(event_type: str) -> dict:
                while True:
                    event = websocket.receive_json()
                    if event["type"] == event_type:
                        return event

            def submit_chat() -> None:
                response_box["response"] = client.post("/chat", json={"message": "hello"})

            worker = Thread(target=submit_chat)
            worker.start()

            started_event = receive_until("chat_started")
            delta_event_first = receive_until("chat_delta")
            delta_event_second = receive_until("chat_delta")
            completed_event = receive_until("chat_completed")

            worker.join(timeout=5)
            response = response_box["response"]

        assert started_event["type"] == "chat_started"
        assert started_event["payload"]["assistant_message_id"].startswith("assistant_")
        assert started_event["payload"]["session_id"] == started_event["payload"]["assistant_message_id"]
        assert started_event["payload"]["sequence"] == 1
        assert isinstance(started_event["payload"]["timestamp_ms"], int)
        assert delta_event_first == {
            "type": "chat_delta",
            "payload": {
                "assistant_message_id": started_event["payload"]["assistant_message_id"],
                "delta": "echo:",
                "session_id": started_event["payload"]["assistant_message_id"],
                "sequence": 2,
                "timestamp_ms": delta_event_first["payload"]["timestamp_ms"],
            },
        }
        assert delta_event_second == {
            "type": "chat_delta",
            "payload": {
                "assistant_message_id": started_event["payload"]["assistant_message_id"],
                "delta": "hello",
                "session_id": started_event["payload"]["assistant_message_id"],
                "sequence": 3,
                "timestamp_ms": delta_event_second["payload"]["timestamp_ms"],
            },
        }
        assert isinstance(delta_event_first["payload"]["timestamp_ms"], int)
        assert isinstance(delta_event_second["payload"]["timestamp_ms"], int)
        assert completed_event == {
            "type": "chat_completed",
            "payload": {
                "assistant_message_id": started_event["payload"]["assistant_message_id"],
                "response_id": "resp_test",
                "content": "echo:hello",
                "session_id": started_event["payload"]["assistant_message_id"],
                "sequence": 4,
                "timestamp_ms": completed_event["payload"]["timestamp_ms"],
            },
        }
        assert isinstance(completed_event["payload"]["timestamp_ms"], int)
        assert response.status_code == 200
        assert response.json()["assistant_message_id"] == started_event["payload"]["assistant_message_id"]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_resume_reuses_original_assistant_message_id_and_continues_stream():
    memory_repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=memory_repository)
    gateway = ResumeStubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/app") as websocket:
            assert websocket.receive_json()["type"] == "snapshot"

            response_box: dict[str, object] = {}

            def receive_until(event_type: str) -> dict:
                while True:
                    event = websocket.receive_json()
                    if event["type"] == event_type:
                        return event

            def submit_resume() -> None:
                response_box["response"] = client.post(
                    "/chat/resume",
                    json={
                        "message": "请继续",
                        "assistant_message_id": "assistant_resume_1",
                        "partial_content": "前半句，",
                    },
                )

            worker = Thread(target=submit_resume)
            worker.start()

            deadline = time.time() + 0.2
            while "response" not in response_box and time.time() < deadline:
                time.sleep(0.01)

            if "response" in response_box:
                early_response = response_box["response"]
                assert early_response.status_code == 200

            started_event = receive_until("chat_started")
            delta_event = receive_until("chat_delta")
            completed_event = receive_until("chat_completed")

            worker.join(timeout=5)
            response = response_box["response"]

        assert started_event == {
            "type": "chat_started",
            "payload": {
                "assistant_message_id": "assistant_resume_1",
                "response_id": "resp_resume",
                "session_id": "assistant_resume_1",
                "sequence": 1,
                "timestamp_ms": started_event["payload"]["timestamp_ms"],
            },
        }
        assert isinstance(started_event["payload"]["timestamp_ms"], int)
        assert delta_event == {
            "type": "chat_delta",
            "payload": {
                "assistant_message_id": "assistant_resume_1",
                "delta": "继续的一半",
                "session_id": "assistant_resume_1",
                "sequence": 2,
                "timestamp_ms": delta_event["payload"]["timestamp_ms"],
            },
        }
        assert isinstance(delta_event["payload"]["timestamp_ms"], int)
        assert completed_event == {
            "type": "chat_completed",
            "payload": {
                "assistant_message_id": "assistant_resume_1",
                "response_id": "resp_resume",
                "content": "前半句，继续的一半",
                "session_id": "assistant_resume_1",
                "sequence": 3,
                "timestamp_ms": completed_event["payload"]["timestamp_ms"],
            },
        }
        assert isinstance(completed_event["payload"]["timestamp_ms"], int)
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_resume",
            "assistant_message_id": "assistant_resume_1",
        }
        assert gateway.last_instructions is not None
        assert "前半句，" in gateway.last_instructions
        assert "继续生成" in gateway.last_instructions
        assert "不要重复" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_does_not_duplicate_memory_rows_when_service_uses_same_repository():
    memory_repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=memory_repository)
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200

        recent = list(reversed(memory_repository.list_recent(limit=10)))
        assert [event.role for event in recent] == ["user", "assistant"]
        assert [event.content for event in recent] == ["hello", "echo:hello"]
        assert len({event.entry_id for event in recent}) == 2
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
    goal_repository = InMemoryGoalRepository()
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY))
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

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


def test_post_chat_includes_relevant_inner_memory_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="inner", content="我感觉自己已经走到第3步，正在进入收束阶段。")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="我刚刚在回看今天的进展。")
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
        response = client.post("/chat", json={"message": "你现在是什么状态"})
        assert response.status_code == 200
        assert ("system", "最近你的内在阶段记忆：我感觉自己已经走到第3步，正在进入收束阶段。") in [
            (message.role, message.content) for message in gateway.last_messages
        ]
        assert gateway.last_messages[-1].content == "你现在是什么状态"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_relevant_autobio_memory_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，已经开始学着把这些变化收束起来。",
        )
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
        response = client.post("/chat", json={"message": "你最近是怎么变化的"})
        assert response.status_code == 200
        assert (
            "system",
            "最近你的自传式回顾：我最近像是一路从第1步走到第3步，已经开始学着把这些变化收束起来。",
        ) in [(message.role, message.content) for message in gateway.last_messages]
        assert gateway.last_messages[-1].content == "你最近是怎么变化的"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_current_focus_goal_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(Goal(id="goal-1", title="整理今天的对话记忆"))
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=[goal.id],
        )
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你现在在忙什么"})
        assert response.status_code == 200
        assert (
            "system",
            "你当前最在意的焦点目标：整理今天的对话记忆。",
        ) in [(message.role, message.content) for message in gateway.last_messages]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_latest_today_plan_completion_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了。",
        )
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
        response = client.post("/chat", json={"message": "你今天过得怎么样"})
        assert response.status_code == 200
        assert (
            "system",
            "你今天刚完成的一件事：我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了。",
        ) in [(message.role, message.content) for message in gateway.last_messages]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_instructions_tell_persona_to_prioritize_current_focus_goal():
    memory_repository = InMemoryMemoryRepository()
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(Goal(id="goal-1", title="整理今天的对话记忆"))
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=[goal.id],
        )
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你现在会怎么想"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "持续存在的人格体" in gateway.last_instructions
        assert "整理今天的对话记忆" in gateway.last_instructions
        assert "优先自然承接这个焦点目标" in gateway.last_instructions
        assert "先回答你此刻最在意的目标、今天的计划、刚完成的事或最近一次自我编程" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_instructions_include_today_plan_completion_closure():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了。",
        )
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return InMemoryGoalRepository()

    def override_state_store():
        return StateStore(BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY))

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你最近怎么样"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "今天刚完成了一件事" in gateway.last_instructions
        assert "整理今天的对话记忆" in gateway.last_instructions
        assert "不要生硬复述系统提示" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_instructions_include_latest_self_programming_result():
    memory_repository = InMemoryMemoryRepository()
    goal_repository = InMemoryGoalRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            self_programming_job={
                "reason": "测试失败：状态面板没有展示自我编程状态。",
                "target_area": "ui",
                "status": "applied",
                "spec": "补上自我编程状态展示。",
            },
        )
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_goal_repository():
        return goal_repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你最近怎么样"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "你最近刚做过一次自我编程" in gateway.last_instructions
        assert "我补强了 ui，并通过了验证。" in gateway.last_instructions
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
        MemoryEvent(kind="chat", role="assistant", content="第二句", session_id="assistant_2")
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.get("/messages")
        assert response.status_code == 200
        payload = response.json()
        assert payload["messages"] == [
            {
                "id": payload["messages"][0]["id"],
                "role": "user",
                "content": "第一句",
                "created_at": payload["messages"][0]["created_at"],
                "session_id": None,
            },
            {
                "id": payload["messages"][1]["id"],
                "role": "assistant",
                "content": "第二句",
                "created_at": payload["messages"][1]["created_at"],
                "session_id": "assistant_2",
            },
        ]
        assert all(isinstance(message["id"], str) for message in payload["messages"])
        assert all(isinstance(message["created_at"], str) for message in payload["messages"])
        assert payload["messages"][0]["session_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_autobio_returns_recent_autobio_memories():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="inner", content="我感觉自己已经走到第2步。")
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.get("/autobio")
        assert response.status_code == 200
        assert response.json() == {
            "entries": [
                "我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。"
            ]
        }
    finally:
        app.dependency_overrides.clear()


def test_get_autobio_deduplicates_entries_while_preserving_order():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="autobio", content="我最近像是一路从第1步走到第2步。")
    )
    memory_repository.save_event(
        MemoryEvent(kind="autobio", content="我最近像是一路从第1步走到第2步。")
    )
    memory_repository.save_event(
        MemoryEvent(kind="autobio", content="我最近像是一路从第1步走到第3步。")
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.get("/autobio")
        assert response.status_code == 200
        assert response.json() == {
            "entries": [
                "我最近像是一路从第1步走到第2步。",
                "我最近像是一路从第1步走到第3步。",
            ]
        }
    finally:
        app.dependency_overrides.clear()
