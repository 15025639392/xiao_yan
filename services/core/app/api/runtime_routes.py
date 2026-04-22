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
    XhsWorkDomainState,
    XhsPublishMode,
    XhsWorkStatus,
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


class XhsWorkDomainUpdateRequest(BaseModel):
    status: str | None = None
    current_focus: str | None = None
    backlog_count: int | None = None
    active_task_ids: list[str] | None = None
    last_published_at: str | None = None
    current_bottleneck: str | None = None
    next_recommended_action: str | None = None
    account_name: str | None = None
    account_positioning: str | None = None
    target_audience: str | None = None
    expression_style: str | None = None
    scouting_interval_hours: float | None = None
    publish_mode: str | None = None
    auto_publish_selector: str | None = None
    north_star: str | None = None
    weekly_goals: list[str] | None = None
    monthly_content_target: int | None = None


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
            last_error=body.last_error if body.last_error is not None else current.last_error,
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

    @router.get("/xhs-work-domain")
    def get_xhs_work_domain(
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        being_state = state_store.get()
        if being_state.xhs_work_domain is None:
            return {"available": False}
        domain = being_state.xhs_work_domain
        return {
            "available": True,
            "profile": {
                "work_type": domain.profile.work_type,
                "account_name": domain.profile.account_name,
                "account_positioning": domain.profile.account_positioning,
                "target_audience": domain.profile.target_audience,
                "expression_style": domain.profile.expression_style,
                "scouting_interval_hours": domain.profile.scouting_interval_hours,
                "publish_mode": domain.profile.publish_mode.value,
                "auto_publish_selector": domain.profile.auto_publish_selector,
            },
            "state": {
                "status": domain.state.status.value,
                "current_focus": domain.state.current_focus,
                "backlog_count": domain.state.backlog_count,
                "active_task_ids": domain.state.active_task_ids,
                "last_published_at": (
                    domain.state.last_published_at.isoformat() if domain.state.last_published_at else None
                ),
                "last_scouting_at": (
                    domain.state.last_scouting_at.isoformat() if domain.state.last_scouting_at else None
                ),
                "current_bottleneck": domain.state.current_bottleneck,
                "next_recommended_action": domain.state.next_recommended_action,
                "review_session_id": domain.state.review_session_id,
                "pending_drafts": domain.state.pending_drafts,
                "published_history": domain.state.published_history,
            },
            "goals": {
                "north_star": domain.goals.north_star,
                "weekly_goals": domain.goals.weekly_goals,
                "monthly_content_target": domain.goals.monthly_content_target,
            },
        }

    @router.patch("/xhs-work-domain")
    def patch_xhs_work_domain(
        update_req: XhsWorkDomainUpdateRequest,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        being_state = state_store.get()
        if being_state.xhs_work_domain is None:
            being_state.xhs_work_domain = XhsWorkDomainState()
        domain = being_state.xhs_work_domain

        if update_req.status is not None:
            domain.state.status = XhsWorkStatus(update_req.status)
            if domain.state.status != XhsWorkStatus.REVIEWING:
                domain.state.review_session_id = ""
        if update_req.current_focus is not None:
            domain.state.current_focus = update_req.current_focus
        if update_req.backlog_count is not None:
            domain.state.backlog_count = update_req.backlog_count
        if update_req.active_task_ids is not None:
            domain.state.active_task_ids = update_req.active_task_ids
        if update_req.last_published_at is not None:
            domain.state.last_published_at = datetime.fromisoformat(update_req.last_published_at)
        if update_req.current_bottleneck is not None:
            domain.state.current_bottleneck = update_req.current_bottleneck
        if update_req.next_recommended_action is not None:
            domain.state.next_recommended_action = update_req.next_recommended_action
        if update_req.account_name is not None:
            domain.profile.account_name = update_req.account_name
        if update_req.account_positioning is not None:
            domain.profile.account_positioning = update_req.account_positioning
        if update_req.target_audience is not None:
            domain.profile.target_audience = update_req.target_audience
        if update_req.expression_style is not None:
            domain.profile.expression_style = update_req.expression_style
        if update_req.scouting_interval_hours is not None:
            domain.profile.scouting_interval_hours = update_req.scouting_interval_hours
        if update_req.publish_mode is not None:
            domain.profile.publish_mode = XhsPublishMode(update_req.publish_mode)
        if update_req.auto_publish_selector is not None:
            domain.profile.auto_publish_selector = update_req.auto_publish_selector
        if update_req.north_star is not None:
            domain.goals.north_star = update_req.north_star
        if update_req.weekly_goals is not None:
            domain.goals.weekly_goals = update_req.weekly_goals
        if update_req.monthly_content_target is not None:
            domain.goals.monthly_content_target = update_req.monthly_content_target

        state_store.set(being_state)
        return {"ok": True}

    return router
