from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect

from app.api.deps import (
    get_memory_repository,
    get_mempalace_adapter,
    get_state_store,
)
from app.llm.schemas import ChatHistoryMessage, ChatHistoryResponse
from app.memory.repository import MemoryRepository
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.runtime import StateStore
from app.runtime_ext.bootstrap import ensure_realtime_hub_initialized, ensure_runtime_initialized
from app.runtime_ext.snapshot import build_public_state_payload, deduplicate_entries


def build_runtime_router() -> APIRouter:
    router = APIRouter()
    DEFAULT_CHAT_MESSAGES_LIMIT = 80

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/environment/mac-console")
    def get_mac_console_environment_status(request: Request) -> dict:
        ensure_runtime_initialized(request.app)
        return (
            getattr(request.app.state, "mac_console_bootstrap_status", None)
            or {
                "state": "unknown",
                "healthy": False,
                "platform": "unknown",
                "enabled": False,
                "attempted_autofix": False,
                "summary": "mac console bootstrap status is unavailable.",
                "checked_at": None,
                "script_path": None,
                "check_exit_code": None,
                "apply_exit_code": None,
            }
        )

    @router.websocket("/ws/app")
    async def app_realtime(websocket: WebSocket) -> None:
        ensure_runtime_initialized(websocket.app)
        ensure_realtime_hub_initialized(websocket.app)
        hub = websocket.app.state.realtime_hub
        connected = await hub.connect(websocket)
        if not connected:
            return

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.disconnect(websocket)

    @router.get("/state")
    def get_state(
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        return build_public_state_payload(state_store.get())

    @router.get("/memory/backends")
    def get_memory_backends(
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
    ) -> dict:
        return {
            "chat_memory": mempalace_adapter.status_snapshot(),
        }

    @router.get("/messages")
    def get_messages(
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
        limit: int = Query(default=DEFAULT_CHAT_MESSAGES_LIMIT, ge=1, le=2000),
        offset: int = Query(default=0, ge=0, le=200000),
    ) -> ChatHistoryResponse:
        recent_chat_events = mempalace_adapter.list_recent_chat_messages(limit=limit + 1, offset=offset)
        has_more = len(recent_chat_events) > limit
        page_events = recent_chat_events[:limit]
        messages = [
            ChatHistoryMessage(
                id=str(event.get("id") or ""),
                role=str(event.get("role") or "assistant"),
                content=str(event.get("content") or ""),
                created_at=event.get("created_at"),
                session_id=event.get("session_id"),
                request_key=event.get("request_key"),
                reasoning_session_id=event.get("reasoning_session_id"),
                reasoning_state=(event.get("reasoning_state") if isinstance(event.get("reasoning_state"), dict) else None),
            )
            for event in reversed(page_events)
            if isinstance(event, dict)
        ]
        next_offset = offset + len(page_events) if has_more else None
        return ChatHistoryResponse(
            messages=messages,
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=next_offset,
        )

    @router.get("/autobio")
    def get_autobio(memory_repository: MemoryRepository = Depends(get_memory_repository)) -> dict[str, list[str]]:
        recent_events = list(reversed(memory_repository.list_recent(limit=20)))
        entries = [event.content for event in recent_events if event.kind == "autobio"]
        return {"entries": deduplicate_entries(entries)}

    return router
