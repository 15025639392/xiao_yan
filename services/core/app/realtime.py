import asyncio
from concurrent.futures import Future
from logging import getLogger
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = getLogger(__name__)


class AppRealtimeHub:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        snapshot_builder: Callable[[], dict[str, Any]],
        *,
        snapshot_cache_ttl_seconds: float = 1.0,
    ) -> None:
        self._loop = loop
        self._snapshot_builder = snapshot_builder
        self._snapshot_cache_ttl_seconds = max(0.0, float(snapshot_cache_ttl_seconds))
        self._snapshot_cached_at: float = 0.0
        self._snapshot_cache: dict[str, Any] | None = None
        self._connections: set[WebSocket] = set()
        # 为每个会话维护序列号计数器
        self._sequence_counters: dict[str, int] = {}

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    async def connect(self, websocket: WebSocket) -> bool:
        await websocket.accept()
        self._connections.add(websocket)
        try:
            await websocket.send_json(
                {
                    "type": "snapshot",
                    "payload": self._get_snapshot(),
                }
            )
        except WebSocketDisconnect:
            self._connections.discard(websocket)
            return False
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    def publish_runtime(self) -> None:
        self._invalidate_snapshot_cache()
        self._schedule_broadcast("runtime_updated", lambda snapshot: snapshot["runtime"])

    def publish_memory(self) -> None:
        self._invalidate_snapshot_cache()
        self._schedule_broadcast("memory_updated", lambda snapshot: snapshot["memory"])

    def publish_persona(self) -> None:
        self._invalidate_snapshot_cache()
        self._schedule_broadcast("persona_updated", lambda snapshot: snapshot["persona"])

    def warm_snapshot_cache(self) -> None:
        self._get_snapshot(force_refresh=True)

    def publish_orchestrator_session_updated(self, payload: Any) -> None:
        self._schedule_payload("orchestrator_session_updated", payload)

    def publish_orchestrator_task_updated(self, payload: Any) -> None:
        self._schedule_payload("orchestrator_task_updated", payload)

    def publish_orchestrator_plan_pending_approval(self, payload: Any) -> None:
        self._schedule_payload("orchestrator_plan_pending_approval", payload)

    def publish_orchestrator_verification_completed(self, payload: Any) -> None:
        self._schedule_payload("orchestrator_verification_completed", payload)

    def publish_orchestrator_message_started(
        self,
        *,
        session_id: str,
        assistant_message_id: str,
        response_id: str | None = None,
    ) -> None:
        seq = self._get_next_sequence(f"orchestrator:{session_id}")
        self._schedule_payload(
            "orchestrator_message_started",
            {
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "response_id": response_id,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_orchestrator_message_delta(
        self,
        *,
        session_id: str,
        assistant_message_id: str,
        delta: str,
    ) -> None:
        seq = self._get_next_sequence(f"orchestrator:{session_id}")
        self._schedule_payload(
            "orchestrator_message_delta",
            {
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "delta": delta,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_orchestrator_message_completed(
        self,
        *,
        session_id: str,
        assistant_message_id: str,
        response_id: str | None,
        content: str,
        blocks: Any,
    ) -> None:
        seq = self._get_next_sequence(f"orchestrator:{session_id}")
        self._schedule_payload(
            "orchestrator_message_completed",
            {
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "response_id": response_id,
                "content": content,
                "blocks": blocks,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_orchestrator_message_failed(
        self,
        *,
        session_id: str,
        assistant_message_id: str,
        error: str,
    ) -> None:
        seq = self._get_next_sequence(f"orchestrator:{session_id}")
        self._schedule_payload(
            "orchestrator_message_failed",
            {
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "error": error,
                "sequence": seq,
                "timestamp_ms": _current_timestamp_ms(),
            },
        )

    def publish_orchestrator_message_appended(self, payload: Any) -> None:
        self._schedule_payload("orchestrator_message_appended", payload)

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
        knowledge_references: list[dict[str, Any]] | None = None,
    ) -> None:
        seq = self._get_next_sequence(session_id or assistant_message_id)
        payload = {
            "assistant_message_id": assistant_message_id,
            "response_id": response_id,
            "content": content,
            "session_id": session_id or assistant_message_id,
            "sequence": seq,
            "timestamp_ms": _current_timestamp_ms(),
        }
        if knowledge_references:
            payload["knowledge_references"] = knowledge_references
        self._schedule_payload("chat_completed", payload)

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

        snapshot = self._get_snapshot()
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

    def _invalidate_snapshot_cache(self) -> None:
        self._snapshot_cache = None
        self._snapshot_cached_at = 0.0

    def _get_snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = monotonic()
        if (
            not force_refresh
            and self._snapshot_cache is not None
            and (now - self._snapshot_cached_at) <= self._snapshot_cache_ttl_seconds
        ):
            return self._snapshot_cache

        snapshot = self._snapshot_builder()
        self._snapshot_cache = snapshot
        self._snapshot_cached_at = now
        return snapshot


def _current_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    import time
    return int(time.time() * 1000)
