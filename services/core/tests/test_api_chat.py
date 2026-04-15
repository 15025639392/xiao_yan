import base64
import os
import sys
import time
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import httpx
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
    get_mempalace_adapter,
    get_memory_repository,
    get_state_store,
)
from app.memory.models import MemoryEvent
from app.memory.observability import KnowledgeObservabilityTracker
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config


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


class ToolCallingStubGateway(StubGateway):
    def __init__(self, expected_read_path: str) -> None:
        super().__init__()
        self.expected_read_path = expected_read_path
        self.tool_output_text: str | None = None
        self.create_calls: list[dict] = []

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        self.create_calls.append(
            {
                "input_items": input_items,
                "instructions": instructions,
                "tools": tools,
                "previous_response_id": previous_response_id,
            }
        )

        has_tool_output = any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for item in input_items
        )

        if not has_tool_output:
            return {
                "id": "resp_tool_1",
                "output": [
                    {
                        "type": "function_call",
                        "id": "fc_1",
                        "call_id": "call_1",
                        "name": "read_file",
                        "arguments": f'{{"path": "{self.expected_read_path}"}}',
                    }
                ],
            }

        tool_outputs = [
            item for item in input_items
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        assert tool_outputs
        latest_tool_output = tool_outputs[-1]
        assert latest_tool_output["call_id"] == "call_1"
        self.tool_output_text = latest_tool_output["output"]
        return {
            "id": "resp_tool_2",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "我已经读取到文件内容。",
                        }
                    ],
                }
            ],
            "output_text": "我已经读取到文件内容。",
        }


class WriteToolCallingStubGateway(StubGateway):
    def __init__(self, target_path: str, content: str) -> None:
        super().__init__()
        self.target_path = target_path
        self.content = content
        self.tool_output_text: str | None = None

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        has_tool_output = any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for item in input_items
        )

        if not has_tool_output:
            return {
                "id": "resp_write_tool_1",
                "output": [
                    {
                        "type": "function_call",
                        "id": "fc_write_1",
                        "call_id": "call_write_1",
                        "name": "write_file",
                        "arguments": (
                            "{"
                            f"\"path\": \"{self.target_path}\", "
                            f"\"content\": \"{self.content}\""
                            "}"
                        ),
                    }
                ],
            }

        tool_outputs = [
            item for item in input_items
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        assert tool_outputs
        latest_tool_output = tool_outputs[-1]
        assert latest_tool_output["call_id"] == "call_write_1"
        self.tool_output_text = latest_tool_output["output"]
        return {
            "id": "resp_write_tool_2",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "写入尝试完成。",
                        }
                    ],
                }
            ],
            "output_text": "写入尝试完成。",
        }


class ToolFallbackResumeStubGateway(StubGateway):
    def __init__(self) -> None:
        super().__init__()
        self.create_call_count = 0
        self.stream_call_count = 0

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        self.create_call_count += 1
        request = httpx.Request("POST", "https://api.minimaxi.com/v1/chat/completions")
        response = httpx.Response(400, request=request, json={"error": {"message": "tools not supported"}})
        raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    def stream_response(self, messages, instructions=None):
        self.stream_call_count += 1
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_resume_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "继续补完",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_resume_fallback",
            "output_text": "继续补完",
        }


class EmptyToolOutputFallbackGateway(StubGateway):
    def __init__(self) -> None:
        super().__init__()
        self.create_call_count = 0
        self.stream_call_count = 0

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        self.create_call_count += 1
        return {"id": "resp_empty_tool", "output": []}

    def stream_response(self, messages, instructions=None):
        self.stream_call_count += 1
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_stream_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "stream-fallback-ok",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_stream_fallback",
            "output_text": "stream-fallback-ok",
        }


class RecursiveToolLoopGateway(StubGateway):
    def __init__(self) -> None:
        super().__init__()
        self.create_call_count = 0
        self.stream_call_count = 0

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        self.create_call_count += 1
        return {
            "id": f"resp_tool_loop_{self.create_call_count}",
            "output": [
                {
                    "type": "function_call",
                    "id": f"fc_loop_{self.create_call_count}",
                    "call_id": f"call_loop_{self.create_call_count}",
                    "name": "unknown_tool",
                    "arguments": "{}",
                }
            ],
        }

    def stream_response(self, messages, instructions=None):
        self.stream_call_count += 1
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_loop_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "我先基于当前上下文直接回答。",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_loop_fallback",
            "output_text": "我先基于当前上下文直接回答。",
        }


class ImageAwareStubGateway(StubGateway):
    def __init__(self) -> None:
        super().__init__()
        self.wire_api = "responses"

    def stream_response(self, messages, instructions=None):
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {
            "type": "response_started",
            "response_id": "resp_image_test",
        }
        yield {
            "type": "text_delta",
            "delta": "已读取图片。",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_image_test",
            "output_text": "已读取图片。",
        }


class StubMemPalaceAdapter:
    def __init__(
        self,
        *,
        search_context_text: str = "",
        raise_on_search: bool = False,
        raise_on_record: bool = False,
        has_cross_room_long_term_sources_value: bool = True,
        chat_history: list[dict[str, str | None]] | None = None,
    ) -> None:
        self.search_context_text = search_context_text
        self.raise_on_search = raise_on_search
        self.raise_on_record = raise_on_record
        self.has_cross_room_long_term_sources_value = has_cross_room_long_term_sources_value
        self.search_queries: list[str] = []
        self.search_exclude_current_room_flags: list[bool] = []
        self.search_max_hits: list[int | None] = []
        self.search_retrieval_weights: list[float | None] = []
        self.cross_room_probe_calls = 0
        self.build_limits: list[int] = []
        self.record_calls: list[tuple[str, str, str | None]] = []
        self.record_attempts = 0
        self.chat_history = [
            {
                "id": str(item.get("id") or f"history_{index}"),
                "role": str(item.get("role") or "assistant"),
                "content": str(item.get("content") or ""),
                "created_at": item.get("created_at"),
                "session_id": item.get("session_id"),
            }
            for index, item in enumerate(chat_history or [])
        ]

    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        self.search_queries.append(query)
        self.search_exclude_current_room_flags.append(exclude_current_room)
        self.search_max_hits.append(max_hits)
        self.search_retrieval_weights.append(retrieval_weight)
        if self.raise_on_search:
            raise RuntimeError("search boom")
        return self.search_context_text

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        _ = cache_seconds
        self.cross_room_probe_calls += 1
        return self.has_cross_room_long_term_sources_value

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        self.build_limits.append(limit)
        recent = self.list_recent_chat_messages(limit=max(1, int(limit)), offset=0)
        messages = [ChatMessage(role=item["role"], content=item["content"]) for item in reversed(recent)]
        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        safe_limit = max(0, int(limit))
        safe_offset = max(0, int(offset))
        if safe_limit == 0:
            return []
        end = len(self.chat_history) - safe_offset
        if end <= 0:
            return []
        start = max(0, end - safe_limit)
        return list(reversed(self.chat_history[start:end]))

    def record_exchange(self, user_message: str, assistant_response: str, assistant_session_id: str | None = None) -> bool:
        self.record_attempts += 1
        if self.raise_on_record:
            raise RuntimeError("record boom")
        self.record_calls.append((user_message, assistant_response, assistant_session_id))
        event_seed = len(self.chat_history)
        self.chat_history.append(
            {
                "id": f"record_{event_seed}_user",
                "role": "user",
                "content": user_message,
                "created_at": None,
                "session_id": None,
            }
        )
        self.chat_history.append(
            {
                "id": f"record_{event_seed}_assistant",
                "role": "assistant",
                "content": assistant_response,
                "created_at": None,
                "session_id": assistant_session_id,
            }
        )
        return True


def test_post_chat_returns_submission_confirmation():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["response_id"] == "resp_test"
        assert response.json()["assistant_message_id"].startswith("assistant_")
        assert mempalace_adapter.record_calls == [
            ("hello", "echo:hello", response.json()["assistant_message_id"])
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_extracts_structured_knowledge_events_when_flag_enabled():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        with patch.dict(os.environ, {"CHAT_KNOWLEDGE_EXTRACTION_ENABLED": "1"}, clear=False):
            response = client.post("/chat", json={"message": "我喜欢结构化输出"})
        assert response.status_code == 200

        recent = memory_repository.list_recent(limit=20, status="all")
        extracted = [event for event in recent if event.kind != "chat"]
        assert any(event.kind == "semantic" and event.knowledge_type == "preference" for event in extracted)
        assert any(event.namespace == "knowledge" for event in extracted)
    finally:
        app.dependency_overrides.clear()


def test_post_chat_injects_only_approved_structured_knowledge_into_instructions():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(search_context_text="")

    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="已审核知识：用户偏好先结论后细节",
            namespace="knowledge",
            review_status="approved",
            source_ref="manual://knowledge",
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="待审核知识：用户偏好超长回复",
            namespace="knowledge",
            review_status="pending_review",
            source_ref="extract://chat",
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="驳回知识：用户不需要上下文",
            namespace="knowledge",
            review_status="rejected",
            source_ref="extract://chat",
        )
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "今天继续聊输出方式"})
        assert response.status_code == 200
        instructions = gateway.last_instructions or ""
        assert "已审核知识：用户偏好先结论后细节" in instructions
        assert "待审核知识：用户偏好超长回复" not in instructions
        assert "驳回知识：用户不需要上下文" not in instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_prioritizes_relevant_approved_knowledge_for_instructions():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(search_context_text="")
    runtime_config = get_runtime_config()
    original_context_limit = runtime_config.chat_context_limit
    runtime_config.chat_context_limit = 3
    now = datetime.now(timezone.utc)

    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="输出规范：先给结论再给细节",
            namespace="knowledge",
            review_status="approved",
            source_ref="manual://style",
            created_at=now - timedelta(days=14),
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="无关知识：用户午饭喜欢米饭",
            namespace="knowledge",
            review_status="approved",
            source_ref="manual://food",
            created_at=now - timedelta(minutes=5),
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="fact",
            content="无关知识：用户常在周三看电影",
            namespace="knowledge",
            review_status="approved",
            source_ref="manual://habit",
            created_at=now - timedelta(minutes=2),
        )
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "后续回答请先给结论再给细节"})
        assert response.status_code == 200
        instructions = gateway.last_instructions or ""
        assert "输出规范：先给结论再给细节" in instructions
        assert "无关知识：用户午饭喜欢米饭" not in instructions
        assert "无关知识：用户常在周三看电影" not in instructions
    finally:
        runtime_config.chat_context_limit = original_context_limit
        app.dependency_overrides.clear()


def test_post_chat_uses_response_completed_output_text_as_final_content():
    memory_repository = InMemoryMemoryRepository()
    gateway = CompletionWinsStubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你好"})
        assert response.status_code == 200
        assert mempalace_adapter.record_calls == [
            ("你好", "你好呀，我是小晏。很高兴见到你～\n\n今天想聊点什么？", response.json()["assistant_message_id"])
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_streams_reply_over_realtime_socket():
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


def test_post_chat_streams_knowledge_references_when_long_term_context_exists():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/knowledge (相似度 0.88) 你喜欢结构化输出。"
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter
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
                response_box["response"] = client.post("/chat", json={"message": "继续按我的偏好来"})

            worker = Thread(target=submit_chat)
            worker.start()

            started_event = receive_until("chat_started")
            receive_until("chat_delta")
            receive_until("chat_delta")
            completed_event = receive_until("chat_completed")

            worker.join(timeout=5)
            response = response_box["response"]

        assert started_event["payload"]["assistant_message_id"].startswith("assistant_")
        assert completed_event["payload"]["knowledge_references"] == [
            {
                "source": "wing_xiaoyan/knowledge",
                "wing": "wing_xiaoyan",
                "room": "knowledge",
                "similarity": 0.88,
                "excerpt": "你喜欢结构化输出。",
            }
        ]
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_post_chat_updates_knowledge_observability_metrics():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/knowledge (相似度 0.88) 你喜欢结构化输出。"
    )
    tracker = KnowledgeObservabilityTracker(max_samples=32)
    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    original_tracker = getattr(app.state, "knowledge_observability_tracker", None)
    try:
        with TestClient(app) as client:
            app.state.knowledge_observability_tracker = tracker
            response = client.post("/chat", json={"message": "继续按我的偏好来"})
            assert response.status_code == 200

            snapshot = tracker.snapshot()
            assert snapshot["latency"]["retrieval_ms"]["count"] == 1
            assert snapshot["latency"]["chat_ms"]["count"] == 1
            assert snapshot["quality"]["queries"] == 1
            assert snapshot["quality"]["hit_queries"] == 1
            assert snapshot["quality"]["avg_similarity"] == 0.88
            assert snapshot["write"]["attempts"] == 1
            assert snapshot["write"]["failures"] == 0
    finally:
        app.dependency_overrides.clear()
        if original_tracker is None:
            delattr(app.state, "knowledge_observability_tracker")
        else:
            app.state.knowledge_observability_tracker = original_tracker


def test_post_chat_skips_cross_room_retrieval_when_no_long_term_sources():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/knowledge (相似度 0.88) 你喜欢结构化输出。",
        has_cross_room_long_term_sources_value=False,
    )
    tracker = KnowledgeObservabilityTracker(max_samples=32)

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    original_tracker = getattr(app.state, "knowledge_observability_tracker", None)
    try:
        with TestClient(app) as client:
            app.state.knowledge_observability_tracker = tracker
            response = client.post("/chat", json={"message": "继续按我的偏好来"})
            assert response.status_code == 200

        assert mempalace_adapter.cross_room_probe_calls == 1
        assert mempalace_adapter.search_queries == []
        snapshot = tracker.snapshot()
        assert snapshot["latency"]["retrieval_ms"]["count"] == 0
        assert snapshot["quality"]["queries"] == 0
    finally:
        app.dependency_overrides.clear()
        if original_tracker is None:
            delattr(app.state, "knowledge_observability_tracker")
        else:
            app.state.knowledge_observability_tracker = original_tracker


def test_knowledge_observability_alerts_require_min_samples():
    tracker = KnowledgeObservabilityTracker(max_samples=64)

    for _ in range(12):
        tracker.record_retrieval(latency_ms=500.0, hit_count=0, failed=False)
        tracker.record_chat_latency(3000.0)
        tracker.record_write(success=True)

    small_sample_snapshot = tracker.snapshot()
    assert small_sample_snapshot["alerts"] == []

    for _ in range(8):
        tracker.record_retrieval(latency_ms=500.0, hit_count=0, failed=False)
        tracker.record_chat_latency(3000.0)
        tracker.record_write(success=True)

    large_sample_snapshot = tracker.snapshot()
    assert "retrieval_p95_above_120ms" in large_sample_snapshot["alerts"]
    assert "chat_p95_above_1500ms" in large_sample_snapshot["alerts"]
    assert "retrieval_hit_rate_below_40pct" in large_sample_snapshot["alerts"]


def test_post_chat_resume_reuses_original_assistant_message_id_and_continues_stream():
    memory_repository = InMemoryMemoryRepository()
    gateway = ResumeStubGateway()

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


def test_post_chat_resume_falls_back_to_plain_stream_when_tools_request_is_rejected():
    memory_repository = InMemoryMemoryRepository()
    gateway = ToolFallbackResumeStubGateway()

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
        response = client.post(
            "/chat/resume",
            json={
                "message": "请继续",
                "assistant_message_id": "assistant_resume_fallback",
                "partial_content": "前半句，",
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_resume_fallback",
            "assistant_message_id": "assistant_resume_fallback",
        }
        assert gateway.create_call_count == 1
        assert gateway.stream_call_count == 1
    finally:
        app.dependency_overrides.clear()


def test_post_chat_falls_back_to_plain_stream_when_tools_response_has_empty_output():
    memory_repository = InMemoryMemoryRepository()
    gateway = EmptyToolOutputFallbackGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_stream_fallback",
            "assistant_message_id": response.json()["assistant_message_id"],
        }
        assert gateway.create_call_count == 1
        assert gateway.stream_call_count == 1
        assert mempalace_adapter.record_calls == [
            ("hello", "stream-fallback-ok", response.json()["assistant_message_id"])
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_falls_back_to_plain_stream_when_tools_enter_recursive_loop():
    memory_repository = InMemoryMemoryRepository()
    gateway = RecursiveToolLoopGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_loop_fallback",
            "assistant_message_id": response.json()["assistant_message_id"],
        }
        assert gateway.stream_call_count == 1
        assert gateway.create_call_count >= 3
        assert mempalace_adapter.record_calls == [
            ("hello", "我先基于当前上下文直接回答。", response.json()["assistant_message_id"])
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_does_not_duplicate_memory_rows_when_service_uses_same_repository():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200

        assert len(mempalace_adapter.record_calls) == 1
        assert mempalace_adapter.record_calls[0][0] == "hello"
        assert mempalace_adapter.record_calls[0][1] == "echo:hello"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_recent_memory_in_gateway_messages():
    memory_repository = InMemoryMemoryRepository()
    goal_repository = InMemoryGoalRepository()
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY))
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        chat_history=[
            {"id": "chat_1", "role": "user", "content": "昨天我们聊了星星", "created_at": "2026-04-10T10:00:00Z"},
            {"id": "chat_2", "role": "assistant", "content": "我记得你喜欢夜空", "created_at": "2026-04-10T10:00:10Z"},
        ]
    )

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

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

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
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        chat_history=[
            {"id": "chat_1", "role": "user", "content": "我们前天讨论过星星和银河", "created_at": "2026-04-09T10:00:00Z"},
            {"id": "chat_2", "role": "assistant", "content": "昨晚我想的是早餐和咖啡", "created_at": "2026-04-10T10:00:00Z"},
            {"id": "chat_3", "role": "user", "content": "今天下午整理了桌面文件", "created_at": "2026-04-11T10:00:00Z"},
        ]
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

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


def test_post_chat_splits_recent_and_long_term_context_budget():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/knowledge (相似度 0.88) 你喜欢结构化输出。"
    )
    runtime_config = get_runtime_config()
    original_context_limit = runtime_config.chat_context_limit
    runtime_config.chat_context_limit = 10

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "继续按我的偏好来"})
        assert response.status_code == 200

        assert mempalace_adapter.build_limits == [7]
        assert mempalace_adapter.search_max_hits == [3]
        assert mempalace_adapter.search_retrieval_weights == [0.3]
        assert mempalace_adapter.search_exclude_current_room_flags == [True]
    finally:
        runtime_config.chat_context_limit = original_context_limit
        app.dependency_overrides.clear()


def test_post_chat_includes_relevant_world_event_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/world (相似度 0.92) 夜里很安静，我有点困，但还惦记着整理今天的对话记忆。"
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你刚刚经历了什么"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "夜里很安静，我有点困，但还惦记着整理今天的对话记忆" in gateway.last_instructions
        assert gateway.last_messages[-1].content == "你刚刚经历了什么"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_relevant_inner_memory_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/inner (相似度 0.90) 我感觉自己已经走到第3步，正在进入收束阶段。"
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你现在是什么状态"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "我感觉自己已经走到第3步，正在进入收束阶段" in gateway.last_instructions
        assert gateway.last_messages[-1].content == "你现在是什么状态"
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_relevant_autobio_memory_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text=(
            "【长期记忆检索】\n- wing_xiaoyan/autobio (相似度 0.89) "
            "我最近像是一路从第1步走到第3步，已经开始学着把这些变化收束起来。"
        )
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你最近是怎么变化的"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "我最近像是一路从第1步走到第3步，已经开始学着把这些变化收束起来" in gateway.last_instructions
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
        assert gateway.last_instructions is not None
        assert "你当前最在意的焦点目标是「整理今天的对话记忆」" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_latest_today_plan_completion_as_system_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text=(
            "【长期记忆检索】\n- wing_xiaoyan/autobio (相似度 0.88) "
            "我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了。"
        )
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你今天过得怎么样"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了" in gateway.last_instructions
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


def test_post_chat_instructions_include_current_thought_for_continuity():
    memory_repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            current_thought="我还在琢磨今天这条线怎么收束。",
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

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你刚刚在想什么"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "你此刻脑海里还有一个没收束的念头" in gateway.last_instructions
        assert "我还在琢磨今天这条线怎么收束" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_updates_current_thought_after_reply():
    memory_repository = InMemoryMemoryRepository()
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY))
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_state_store():
        return state_store

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "今天先做哪一步"})
        assert response.status_code == 200

        current_state = state_store.get()
        assert current_state.current_thought is not None
        assert "今天先做哪一步" in current_state.current_thought
    finally:
        app.dependency_overrides.clear()


def test_post_chat_can_override_mempalace_adapter_dependency():
    class _StubMemPalaceAdapter:
        def search_context(
            self,
            query: str,
            *,
            exclude_current_room: bool = False,
            max_hits: int | None = None,
            retrieval_weight: float | None = None,
        ) -> str:
            return ""

        def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
            return [ChatMessage(role="user", content=user_message)]

        def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
            return []

        def record_exchange(self, user_message: str, assistant_response: str, assistant_session_id: str | None = None) -> bool:
            return True

    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = _StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_post_chat_instructions_include_mempalace_context_when_available():
    from app.api.deps import get_mempalace_adapter

    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text="【长期记忆检索】\n- wing_xiaoyan/relationship (相似度 0.91) 我们聊过星星和夜空。"
    )

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你还记得我们聊过的星星吗"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
        assert "【长期记忆检索】" in gateway.last_instructions
        assert "我们聊过星星和夜空" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_mirrors_exchange_to_mempalace_when_enabled():
    from app.api.deps import get_mempalace_adapter

    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert len(mempalace_adapter.record_calls) == 1
        user_message, assistant_response, assistant_session_id = mempalace_adapter.record_calls[0]
        assert user_message == "hello"
        assert assistant_response == "echo:hello"
        assert isinstance(assistant_session_id, str)
        assert assistant_session_id.startswith("assistant_")
    finally:
        app.dependency_overrides.clear()


def test_chat_still_returns_200_when_mempalace_search_raises():
    from app.api.deps import get_mempalace_adapter

    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(raise_on_search=True)

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert mempalace_adapter.search_queries == ["hello"]
        assert mempalace_adapter.search_exclude_current_room_flags == [True]
    finally:
        app.dependency_overrides.clear()


def test_chat_still_returns_200_when_mempalace_record_raises():
    from app.api.deps import get_mempalace_adapter

    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(raise_on_record=True)

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert mempalace_adapter.record_attempts == 1
    finally:
        app.dependency_overrides.clear()


def test_post_chat_instructions_include_today_plan_completion_closure():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter(
        search_context_text=(
            "【长期记忆检索】\n- wing_xiaoyan/autobio (相似度 0.88) "
            "我把今天的计划“整理今天的对话记忆”完整走完了，感觉这一轮心里更有数了。"
        )
    )

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

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_goal_repository] = override_goal_repository
    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "你最近怎么样"})
        assert response.status_code == 200
        assert gateway.last_instructions is not None
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
    mempalace_adapter = StubMemPalaceAdapter(
        chat_history=[
            {
                "id": "chat_1",
                "role": "user",
                "content": "第一句",
                "created_at": "2026-04-11T10:00:00Z",
                "session_id": None,
            },
            {
                "id": "chat_2",
                "role": "assistant",
                "content": "第二句",
                "created_at": "2026-04-11T10:00:05Z",
                "session_id": "assistant_2",
            },
        ]
    )

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

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


def test_get_messages_supports_pagination_with_offset():
    memory_repository = InMemoryMemoryRepository()
    mempalace_adapter = StubMemPalaceAdapter(
        chat_history=[
            {"id": f"chat_{index}", "role": "user", "content": f"第{index}句", "created_at": f"2026-04-11T10:00:0{index}Z"}
            for index in range(1, 7)
        ]
    )

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)

        page_1 = client.get("/messages?limit=2&offset=0")
        assert page_1.status_code == 200
        payload_1 = page_1.json()
        assert [item["content"] for item in payload_1["messages"]] == ["第5句", "第6句"]
        assert payload_1["has_more"] is True
        assert payload_1["next_offset"] == 2

        page_2 = client.get("/messages?limit=2&offset=2")
        assert page_2.status_code == 200
        payload_2 = page_2.json()
        assert [item["content"] for item in payload_2["messages"]] == ["第3句", "第4句"]
        assert payload_2["has_more"] is True
        assert payload_2["next_offset"] == 4

        page_3 = client.get("/messages?limit=2&offset=4")
        assert page_3.status_code == 200
        payload_3 = page_3.json()
        assert [item["content"] for item in payload_3["messages"]] == ["第1句", "第2句"]
        assert payload_3["has_more"] is False
        assert payload_3["next_offset"] is None
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


def test_chat_folder_permissions_crud():
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        client = TestClient(app)
        assert client.get("/chat/folder-permissions").status_code == 200
        assert client.get("/chat/folder-permissions").json() == {"permissions": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir).resolve()

            response = client.put(
                "/chat/folder-permissions",
                json={"path": str(folder), "access_level": "read_only"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "permissions": [
                    {"path": str(folder), "access_level": "read_only"},
                ]
            }

            response = client.put(
                "/chat/folder-permissions",
                json={"path": str(folder), "access_level": "full_access"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "permissions": [
                    {"path": str(folder), "access_level": "full_access"},
                ]
            }

            delete_resp = client.delete(
                "/chat/folder-permissions",
                params={"path": str(folder)},
            )
            assert delete_resp.status_code == 200
            assert delete_resp.json() == {"permissions": []}
    finally:
        config.clear_folder_permissions()


def test_chat_folder_permissions_rejects_invalid_directory():
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.txt"
            file_path.write_text("hello", encoding="utf-8")
            missing_path = Path(tmpdir) / "missing"
            relative_path = "relative/path"

            file_resp = client.put(
                "/chat/folder-permissions",
                json={"path": str(file_path), "access_level": "read_only"},
            )
            assert file_resp.status_code == 400
            assert file_resp.json()["detail"] == "path is not a directory"

            missing_resp = client.put(
                "/chat/folder-permissions",
                json={"path": str(missing_path), "access_level": "full_access"},
            )
            assert missing_resp.status_code == 404
            assert missing_resp.json()["detail"] == "folder not found"

            relative_resp = client.put(
                "/chat/folder-permissions",
                json={"path": relative_path, "access_level": "read_only"},
            )
            assert relative_resp.status_code == 400
            assert relative_resp.json()["detail"] == "folder path must be absolute"
    finally:
        config.clear_folder_permissions()


def test_post_chat_instructions_include_granted_folder_permissions():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    config = get_runtime_config()
    config.clear_folder_permissions()

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
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir).resolve()
            config.set_folder_permission(str(folder), "read_only")
            client = TestClient(app)
            response = client.post("/chat", json={"message": "帮我看下这个目录"})
            assert response.status_code == 200
            assert gateway.last_instructions is not None
            assert "你当前可访问的文件夹权限如下" in gateway.last_instructions
            assert str(folder) in gateway.last_instructions
            assert "read_only（只读）" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()
        config.clear_folder_permissions()


def test_post_chat_executes_file_tools_when_gateway_requests_function_call():
    memory_repository = InMemoryMemoryRepository()
    mempalace_adapter = StubMemPalaceAdapter()
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir).resolve()
            target_file = folder / "notes.txt"
            target_file.write_text("hello from tool", encoding="utf-8")
            config.set_folder_permission(str(folder), "read_only")

            gateway = ToolCallingStubGateway(str(target_file))

            def override_gateway():
                try:
                    yield gateway
                finally:
                    gateway.close()

            def override_memory_repository():
                return memory_repository

            def override_mempalace_adapter():
                return mempalace_adapter

            app.dependency_overrides[get_chat_gateway] = override_gateway
            app.dependency_overrides[get_memory_repository] = override_memory_repository
            app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

            client = TestClient(app)
            response = client.post("/chat", json={"message": "请读取我授权目录里的 notes.txt"})
            assert response.status_code == 200
            assert response.json()["response_id"] == "resp_tool_2"
            assert gateway.tool_output_text is not None
            assert "hello from tool" in gateway.tool_output_text
            assert mempalace_adapter.record_calls == [
                ("请读取我授权目录里的 notes.txt", "我已经读取到文件内容。", response.json()["assistant_message_id"])
            ]
    finally:
        app.dependency_overrides.clear()
        config.clear_folder_permissions()


def test_post_chat_write_file_tool_respects_read_only_folder_permission():
    memory_repository = InMemoryMemoryRepository()
    mempalace_adapter = StubMemPalaceAdapter()
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir).resolve()
            target_file = folder / "blocked.txt"
            config.set_folder_permission(str(folder), "read_only")

            gateway = WriteToolCallingStubGateway(str(target_file), "should-not-write")

            def override_gateway():
                try:
                    yield gateway
                finally:
                    gateway.close()

            def override_memory_repository():
                return memory_repository

            def override_mempalace_adapter():
                return mempalace_adapter

            app.dependency_overrides[get_chat_gateway] = override_gateway
            app.dependency_overrides[get_memory_repository] = override_memory_repository
            app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

            client = TestClient(app)
            response = client.post("/chat", json={"message": "请写入这个文件"})
            assert response.status_code == 200
            assert gateway.tool_output_text is not None
            assert "write not allowed" in gateway.tool_output_text
            assert not target_file.exists()
    finally:
        app.dependency_overrides.clear()
        config.clear_folder_permissions()


def test_post_chat_attached_folder_is_added_to_permissions_and_prompt_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()
    config = get_runtime_config()
    original_permissions = config.list_folder_permissions()
    config.clear_folder_permissions()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            attached_folder = str(Path(temp_dir).resolve())

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={
                    "message": "帮我先看看这个项目目录",
                    "attachments": [
                        {
                            "type": "folder",
                            "path": attached_folder,
                        }
                    ],
                },
            )

            assert response.status_code == 200
            assert gateway.last_instructions is not None
            assert "本轮用户附加了这些文件夹上下文" in gateway.last_instructions
            assert f"- {attached_folder}" in gateway.last_instructions
            assert "read_only（只读）" in gateway.last_instructions
            assert (attached_folder, "read_only") in config.list_folder_permissions()
    finally:
        app.dependency_overrides.clear()
        config.clear_folder_permissions()
        for folder_path, access_level in original_permissions:
            config.set_folder_permission(folder_path, access_level)


def test_post_chat_attached_file_is_injected_into_user_context():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()
    config = get_runtime_config()
    original_permissions = config.list_folder_permissions()
    config.clear_folder_permissions()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            attached_file = Path(temp_dir).resolve() / "notes.md"
            attached_file.write_text("这是文件里的关键内容。", encoding="utf-8")

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={
                    "message": "请基于附件回答",
                    "attachments": [
                        {
                            "type": "file",
                            "path": str(attached_file),
                        }
                    ],
                },
            )

            assert response.status_code == 200
            assert gateway.last_messages
            last_content = gateway.last_messages[-1].content
            assert isinstance(last_content, str)
            assert "[用户附加文件内容摘录]" in last_content
            assert "这是文件里的关键内容。" in last_content
            assert (str(attached_file.parent), "read_only") in config.list_folder_permissions()
    finally:
        app.dependency_overrides.clear()
        config.clear_folder_permissions()
        for folder_path, access_level in original_permissions:
            config.set_folder_permission(folder_path, access_level)


def test_post_chat_rejects_image_attachment_for_nvidia_provider():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model

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
        config.chat_provider = "nvidia"
        config.chat_model = "meta/llama-3.1-70b-instruct"
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir).resolve() / "sample.png"
            image_path.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6XgnQAAAAASUVORK5CYII="
                )
            )

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={
                    "message": "看下这张图",
                    "attachments": [
                        {
                            "type": "image",
                            "path": str(image_path),
                        }
                    ],
                },
            )

            assert response.status_code == 400
            assert "does not support image attachments" in response.json()["detail"]
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model
        app.dependency_overrides.clear()


def test_post_chat_accepts_image_attachment_for_supported_model():
    memory_repository = InMemoryMemoryRepository()
    gateway = ImageAwareStubGateway()
    config = get_runtime_config()
    original_provider = config.chat_provider
    original_model = config.chat_model

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
        config.chat_provider = "openai"
        config.chat_model = "gpt-5.4"
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir).resolve() / "sample.png"
            image_path.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6XgnQAAAAASUVORK5CYII="
                )
            )

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={
                    "message": "看下这张图",
                    "attachments": [
                        {
                            "type": "image",
                            "path": str(image_path),
                        }
                    ],
                },
            )

            assert response.status_code == 200
            assert gateway.last_messages
            last_content = gateway.last_messages[-1].content
            assert isinstance(last_content, list)
            assert any(
                isinstance(item, dict) and item.get("type") == "input_image"
                for item in last_content
            )
    finally:
        config.chat_provider = original_provider
        config.chat_model = original_model
        app.dependency_overrides.clear()


def test_post_chat_uses_chat_model_from_runtime_config():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    gateway.model = "gpt-legacy"
    config = get_runtime_config()
    original_model = config.chat_model

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
        config.chat_model = "gpt-5.4-mini"
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert gateway.model == "gpt-5.4-mini"
    finally:
        config.chat_model = original_model
        app.dependency_overrides.clear()


def test_get_chat_skills_returns_discovered_skills():
    with tempfile.TemporaryDirectory() as temp_dir:
        skill_root = Path(temp_dir).resolve()
        skill_dir = skill_root / "requirement-workflow"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: requirement-workflow\n"
            "description: 需求分析工作流\n"
            "---\n\n"
            "# Requirement Workflow\n"
            "先做需求澄清再输出方案。\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"CHAT_SKILL_ROOTS": str(skill_root)}):
            client = TestClient(app)
            response = client.get("/chat/skills")
            assert response.status_code == 200
            payload = response.json()
            assert payload["skills"]
            matched = next((item for item in payload["skills"] if item["name"] == "requirement-workflow"), None)
            assert matched is not None
            assert matched["description"] == "需求分析工作流"
            assert matched["path"] == str((skill_dir / "SKILL.md").resolve())
            assert "需求:" in matched["trigger_prefixes"]


def test_post_chat_injects_skill_instructions_when_message_mentions_skill():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir).resolve()
            skill_dir = skill_root / "requirement-workflow"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: requirement-workflow\n"
                "description: 需求分析工作流\n"
                "---\n\n"
                "# Requirement Workflow\n"
                "必须先澄清约束，再给方案。\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"CHAT_SKILL_ROOTS": str(skill_root)}):
                client = TestClient(app)
                response = client.post("/chat", json={"message": "请用 $requirement-workflow 分析这个需求"})
                assert response.status_code == 200
                assert gateway.last_instructions is not None
                assert "[Skills]" in gateway.last_instructions
                assert "[Skill: requirement-workflow]" in gateway.last_instructions
                assert "必须先澄清约束，再给方案。" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()


def test_post_chat_injects_skill_instructions_when_message_matches_prefix_trigger():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir).resolve()
            skill_dir = skill_root / "requirement-workflow"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: requirement-workflow\n"
                "description: 需求分析工作流\n"
                "---\n\n"
                "# Requirement Workflow\n"
                "先确认目标，再拆解范围。\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"CHAT_SKILL_ROOTS": str(skill_root)}):
                client = TestClient(app)
                response = client.post("/chat", json={"message": "需求: 帮我拆解地图知识库方案"})
                assert response.status_code == 200
                assert gateway.last_instructions is not None
                assert "[Skill: requirement-workflow]" in gateway.last_instructions
                assert "先确认目标，再拆解范围。" in gateway.last_instructions
    finally:
        app.dependency_overrides.clear()

class McpToolCallingStubGateway(StubGateway):
    def __init__(self, tool_name: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_output_text: str | None = None

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        has_tool_output = any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for item in input_items
        )

        if not has_tool_output:
            return {
                "id": "resp_mcp_tool_1",
                "output": [
                    {
                        "type": "function_call",
                        "id": "fc_mcp_1",
                        "call_id": "call_mcp_1",
                        "name": self.tool_name,
                        "arguments": '{"text": "hello mcp"}',
                    }
                ],
            }

        tool_outputs = [
            item for item in input_items
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        assert tool_outputs
        self.tool_output_text = str(tool_outputs[-1].get("output"))
        return {
            "id": "resp_mcp_tool_2",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "MCP 已执行。",
                        }
                    ],
                }
            ],
            "output_text": "MCP 已执行。",
        }


def test_get_chat_mcp_servers_returns_runtime_snapshot():
    config = get_runtime_config()
    original_enabled = config.chat_mcp_enabled
    original_servers = config.list_chat_mcp_servers()

    try:
        config.chat_mcp_enabled = True
        config.replace_chat_mcp_servers(
            [
                {
                    "server_id": "filesystem",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                    "enabled": True,
                    "timeout_seconds": 20,
                }
            ]
        )

        client = TestClient(app)
        response = client.get("/chat/mcp/servers")
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["servers"]
        assert body["servers"][0]["server_id"] == "filesystem"
        assert body["servers"][0]["command"] == "npx"
    finally:
        config.chat_mcp_enabled = original_enabled
        config.replace_chat_mcp_servers(original_servers)


def test_post_chat_executes_mcp_tool_when_server_is_selected():
    memory_repository = InMemoryMemoryRepository()
    config = get_runtime_config()
    original_enabled = config.chat_mcp_enabled
    original_servers = config.list_chat_mcp_servers()

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir).resolve() / "mcp_echo_server.py"
        script_path.write_text(
            (
                "import json\n"
                "import sys\n"
                "\n"
                "def read_msg():\n"
                "    headers = {}\n"
                "    while True:\n"
                "        line = sys.stdin.buffer.readline()\n"
                "        if not line:\n"
                "            return None\n"
                "        if line in (b'\\r\\n', b'\\n'):\n"
                "            break\n"
                "        decoded = line.decode('utf-8').strip()\n"
                "        if ':' not in decoded:\n"
                "            continue\n"
                "        key, value = decoded.split(':', 1)\n"
                "        headers[key.strip().lower()] = value.strip()\n"
                "    length = int(headers.get('content-length', '0'))\n"
                "    body = sys.stdin.buffer.read(length)\n"
                "    return json.loads(body.decode('utf-8'))\n"
                "\n"
                "def write_msg(payload):\n"
                "    body = json.dumps(payload).encode('utf-8')\n"
                "    sys.stdout.buffer.write(f'Content-Length: {len(body)}\\r\\n\\r\\n'.encode('ascii'))\n"
                "    sys.stdout.buffer.write(body)\n"
                "    sys.stdout.buffer.flush()\n"
                "\n"
                "while True:\n"
                "    msg = read_msg()\n"
                "    if msg is None:\n"
                "        break\n"
                "    method = msg.get('method')\n"
                "    request_id = msg.get('id')\n"
                "    if method == 'initialize':\n"
                "        write_msg({'jsonrpc': '2.0', 'id': request_id, 'result': {'capabilities': {}}})\n"
                "    elif method == 'tools/list':\n"
                "        write_msg({'jsonrpc': '2.0', 'id': request_id, 'result': {'tools': [{'name': 'echo_tool', 'description': 'echo text', 'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text'], 'additionalProperties': False}}]}})\n"
                "    elif method == 'tools/call':\n"
                "        params = msg.get('params') or {}\n"
                "        arguments = params.get('arguments') or {}\n"
                "        text = arguments.get('text', '')\n"
                "        write_msg({'jsonrpc': '2.0', 'id': request_id, 'result': {'content': [{'type': 'text', 'text': f'mcp:{text}'}]}})\n"
                "    elif request_id is not None:\n"
                "        write_msg({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32601, 'message': 'method not found'}})\n"
            ),
            encoding="utf-8",
        )

        gateway = McpToolCallingStubGateway("mcp__test_server__echo_tool")
        mempalace_adapter = StubMemPalaceAdapter()

        def override_gateway():
            try:
                yield gateway
            finally:
                gateway.close()

        def override_memory_repository():
            return memory_repository

        def override_mempalace_adapter():
            return mempalace_adapter

        app.dependency_overrides[get_chat_gateway] = override_gateway
        app.dependency_overrides[get_memory_repository] = override_memory_repository
        app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

        try:
            config.chat_mcp_enabled = True
            config.replace_chat_mcp_servers(
                [
                    {
                        "server_id": "test-server",
                        "command": sys.executable,
                        "args": [str(script_path)],
                        "enabled": True,
                        "timeout_seconds": 20,
                    }
                ]
            )

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={
                    "message": "请通过 mcp 回答",
                    "mcp_servers": ["test-server"],
                },
            )
            assert response.status_code == 200
            assert gateway.tool_output_text is not None
            assert "mcp:hello mcp" in gateway.tool_output_text
        finally:
            config.chat_mcp_enabled = original_enabled
            config.replace_chat_mcp_servers(original_servers)
            app.dependency_overrides.clear()
