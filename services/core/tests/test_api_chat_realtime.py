import time
from threading import Thread

import httpx
from fastapi.testclient import TestClient

from app.main import app, get_chat_gateway, get_memory_repository, get_mempalace_adapter
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime_ext.runtime_config import get_runtime_config


class ToolFallbackResumeRealtimeGateway:
    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
        response = httpx.Response(400, request=request, json={"error": {"message": "tools not supported"}})
        raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    def stream_response(self, messages, instructions=None):
        _ = (messages, instructions)
        yield {
            "type": "response_started",
            "response_id": "resp_resume_fallback_ws",
        }
        yield {
            "type": "text_delta",
            "delta": "继续补完",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_resume_fallback_ws",
            "output_text": "继续补完",
        }

    def close(self) -> None:
        return None


class StubMemPalaceAdapter:
    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        _ = (query, exclude_current_room, max_hits, retrieval_weight)
        return ""

    def build_chat_messages(self, user_message: str, *, limit: int):
        _ = (user_message, limit)
        return []

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0):
        _ = (limit, offset)
        return []

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        request_key: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        _ = (
            user_message,
            assistant_response,
            assistant_session_id,
            request_key,
            reasoning_session_id,
            reasoning_state,
        )
        return True


def test_resume_tool_fallback_realtime_events_preserve_request_key_and_reasoning_state():
    memory_repository = InMemoryMemoryRepository()
    gateway = ToolFallbackResumeRealtimeGateway()
    mempalace_adapter = StubMemPalaceAdapter()
    runtime_config = get_runtime_config()
    original_enabled = runtime_config.chat_continuous_reasoning_enabled

    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            role="assistant",
            content="这是上一轮推理结果",
            session_id="assistant_resume_realtime_1",
            reasoning_session_id="reasoning_resume_realtime_1",
            reasoning_state={
                "session_id": "reasoning_resume_realtime_1",
                "phase": "exploring",
                "step_index": 2,
                "summary": "已经推进到第2步",
                "updated_at": "2026-04-16T10:00:00+00:00",
            },
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
    runtime_config.chat_continuous_reasoning_enabled = True

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
                        "assistant_message_id": "assistant_resume_realtime_1",
                        "partial_content": "前半句，",
                        "request_key": "request_resume_realtime_1",
                    },
                )

            worker = Thread(target=submit_resume)
            worker.start()

            deadline = time.time() + 0.2
            while "response" not in response_box and time.time() < deadline:
                time.sleep(0.01)

            started_event = receive_until("chat_started")
            delta_event = receive_until("chat_delta")
            completed_event = receive_until("chat_completed")

            worker.join(timeout=5)
            response = response_box["response"]

        assert response.status_code == 200
        payload = response.json()
        assert payload["response_id"] == "resp_resume_fallback_ws"
        assert payload["request_key"] == "request_resume_realtime_1"
        assert payload["reasoning_session_id"] == "reasoning_resume_realtime_1"
        assert payload["reasoning_state"]["step_index"] == 3

        assert started_event["payload"]["request_key"] == "request_resume_realtime_1"
        assert started_event["payload"]["reasoning_session_id"] == "reasoning_resume_realtime_1"
        assert started_event["payload"]["reasoning_state"]["step_index"] == 3

        assert delta_event["payload"]["request_key"] == "request_resume_realtime_1"
        assert delta_event["payload"]["reasoning_session_id"] == "reasoning_resume_realtime_1"
        assert delta_event["payload"]["reasoning_state"]["step_index"] == 3
        assert delta_event["payload"]["delta"] == "继续补完"

        assert completed_event["payload"]["request_key"] == "request_resume_realtime_1"
        assert completed_event["payload"]["reasoning_session_id"] == "reasoning_resume_realtime_1"
        assert completed_event["payload"]["reasoning_state"]["step_index"] == 3
        assert completed_event["payload"]["content"] == "前半句，继续补完"
    finally:
        runtime_config.chat_continuous_reasoning_enabled = original_enabled
        app.dependency_overrides.clear()
