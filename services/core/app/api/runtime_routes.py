from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.api.deps import (
    get_memory_repository,
    get_mempalace_adapter,
    get_state_store,
)
from app.domain.models import (
    BrowserInteractionLevel,
    BrowserOrganBindingStatus,
    BrowserOrganHealthStatus,
    BrowserOrganState,
    BrowserSessionState,
    BrowserSessionStatus,
)
from app.llm.schemas import ChatHistoryMessage, ChatHistoryResponse
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.runtime_ext.bootstrap import ensure_realtime_hub_initialized, ensure_runtime_initialized
from app.runtime_ext.snapshot import build_public_state_payload, deduplicate_entries


class BrowserOrganUpdateRequest(BaseModel):
    binding_status: str | None = None
    health_status: str | None = None
    driver_name: str | None = None
    driver_version: str | None = None
    browser_binary_ready: bool | None = None
    requires_approval_for_bind: bool | None = None
    last_error: str | None = None


class BrowserSessionUpdateRequest(BaseModel):
    session_id: str | None = None
    status: str | None = None
    current_url: str | None = None
    page_title: str | None = None
    opened_at: str | None = None
    interaction_level: str | None = None
    last_snapshot_summary: str | None = None
    last_error: str | None = None


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

    @router.post("/browser/organ")
    def update_browser_organ(
        body: BrowserOrganUpdateRequest,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        being_state = state_store.get()
        current = being_state.browser_organ or BrowserOrganState()
        updated = BrowserOrganState(
            knowledge_status=current.knowledge_status,
            binding_status=BrowserOrganBindingStatus(body.binding_status or current.binding_status.value),
            health_status=BrowserOrganHealthStatus(body.health_status or current.health_status.value),
            last_checked_at=datetime.now(timezone.utc),
            driver_name=body.driver_name or current.driver_name,
            driver_version=body.driver_version or current.driver_version,
            browser_binary_ready=(
                body.browser_binary_ready if body.browser_binary_ready is not None else current.browser_binary_ready
            ),
            requires_approval_for_bind=(
                body.requires_approval_for_bind if body.requires_approval_for_bind is not None else current.requires_approval_for_bind
            ),
            last_error=body.last_error or current.last_error,
        )
        being_state.browser_organ = updated
        state_store.set(being_state)
        return {"ok": True}

    @router.post("/browser/session")
    def update_browser_session(
        body: BrowserSessionUpdateRequest,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        being_state = state_store.get()
        updated = BrowserSessionState(
            session_id=body.session_id or "none",
            status=BrowserSessionStatus(body.status or "closed"),
            current_url=body.current_url,
            page_title=body.page_title,
            opened_at=body.opened_at,
            last_active_at=datetime.now(timezone.utc),
            interaction_level=BrowserInteractionLevel(body.interaction_level or "read_only"),
            last_snapshot_summary=body.last_snapshot_summary,
            last_error=body.last_error,
        )
        being_state.browser_session = updated
        state_store.set(being_state)
        return {"ok": True}

    return router
