import asyncio
from concurrent.futures import Future
from logging import getLogger
from typing import Any, Callable
from uuid import uuid4

from fastapi import WebSocket

logger = getLogger(__name__)


class AppRealtimeHub:
    def __init__(self, loop: asyncio.AbstractEventLoop, snapshot_builder: Callable[[], dict[str, Any]]) -> None:
        self._loop = loop
        self._snapshot_builder = snapshot_builder
        self._connections: set[WebSocket] = set()
        # 为每个会话维护序列号计数器
        self._sequence_counters: dict[str, int] = {}

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        await websocket.send_json(
            {
                "type": "snapshot",
                "payload": self._snapshot_builder(),
            }
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    def publish_runtime(self) -> None:
        self._schedule_broadcast("runtime_updated", lambda snapshot: snapshot["runtime"])

    def publish_memory(self) -> None:
        self._schedule_broadcast("memory_updated", lambda snapshot: snapshot["memory"])

    def publish_persona(self) -> None:
        self._schedule_broadcast("persona_updated", lambda snapshot: snapshot["persona"])

    def publish_chat_started(
        self,
        assistant_message_id: str,
        response_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        seq = self._get_next_sequence(session_id or assistant_message_id)
        self._schedule_payload(
            "chat_started",
            {
                "assistant_message_id": assistant_message_id,
                "response_id": response_id,
                "session_id": session_id or assistant_message_id,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_chat_delta(
        self,
        assistant_message_id: str,
        delta: str,
        session_id: str | None = None,
    ) -> None:
        seq = self._get_next_sequence(session_id or assistant_message_id)
        self._schedule_payload(
            "chat_delta",
            {
                "assistant_message_id": assistant_message_id,
                "delta": delta,
                "session_id": session_id or assistant_message_id,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_chat_completed(
        self,
        assistant_message_id: str,
        response_id: str | None,
        content: str,
        session_id: str | None = None,
    ) -> None:
        seq = self._get_next_sequence(session_id or assistant_message_id)
        self._schedule_payload(
            "chat_completed",
            {
                "assistant_message_id": assistant_message_id,
                "response_id": response_id,
                "content": content,
                "session_id": session_id or assistant_message_id,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_chat_failed(
        self,
        assistant_message_id: str,
        error: str,
        session_id: str | None = None,
    ) -> None:
        seq = self._get_next_sequence(session_id or assistant_message_id)
        self._schedule_payload(
            "chat_failed",
            {
                "assistant_message_id": assistant_message_id,
                "error": error,
                "session_id": session_id or assistant_message_id,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def _schedule_broadcast(
        self,
        event_type: str,
        payload_selector: Callable[[dict[str, Any]], Any],
    ) -> None:
        if self._loop.is_closed():
            return

        future: Future[None] = asyncio.run_coroutine_threadsafe(
            self._broadcast(event_type, payload_selector),
            self._loop,
        )
        future.add_done_callback(self._log_future_error)

    def _schedule_payload(self, event_type: str, payload: Any) -> None:
        if self._loop.is_closed():
            return

        future: Future[None] = asyncio.run_coroutine_threadsafe(
            self._broadcast_payload(event_type, payload),
            self._loop,
        )
        future.add_done_callback(self._log_future_error)

    async def _broadcast(
        self,
        event_type: str,
        payload_selector: Callable[[dict[str, Any]], Any],
    ) -> None:
        if not self._connections:
            return

        snapshot = self._snapshot_builder()
        payload = payload_selector(snapshot)
        stale_connections: list[WebSocket] = []

        for websocket in list(self._connections):
            try:
                await websocket.send_json(
                    {
                        "type": event_type,
                        "payload": payload,
                    }
                )
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self._connections.discard(websocket)

    async def _broadcast_payload(self, event_type: str, payload: Any) -> None:
        if not self._connections:
            return

        stale_connections: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(
                    {
                        "type": event_type,
                        "payload": payload,
                    }
                )
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self._connections.discard(websocket)

    @staticmethod
    def _log_future_error(future: Future[None]) -> None:
        exception = future.exception()
        if exception is not None:
            logger.warning("Realtime broadcast failed: %s", exception)

    def _get_next_sequence(self, session_id: str) -> int:
        """获取指定会话的下一个序列号"""
        if session_id not in self._sequence_counters:
            self._sequence_counters[session_id] = 0
        self._sequence_counters[session_id] += 1
        return self._sequence_counters[session_id]


def _current_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    import time
    return int(time.time() * 1000)
