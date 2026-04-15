from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_memory_service
from app.memory.models import MemoryEvent, MemoryKind
from app.memory.service import MemoryService


class KnowledgeCreateRequest(BaseModel):
    kind: MemoryKind = MemoryKind.FACT
    content: str = Field(..., min_length=1)
    role: str | None = None
    knowledge_type: str | None = None
    knowledge_tags: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    version_tag: str | None = None
    visibility: Literal["internal", "user"] = "user"
    reviewer: str | None = None
    review_note: str | None = None


class KnowledgeReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "pend"]
    reviewer: str | None = None
    review_note: str | None = None


class KnowledgeBatchReviewRequest(BaseModel):
    knowledge_ids: list[str] = Field(default_factory=list)
    decision: Literal["approve", "reject", "pend"]
    reviewer: str | None = None
    review_note: str | None = None


def build_knowledge_router() -> APIRouter:
    router = APIRouter()
    missing_datetime_sort_value = -1.0e15

    def _serialize_event(event: MemoryEvent) -> dict:
        return {
            "id": event.entry_id,
            "kind": event.kind,
            "content": event.content,
            "role": event.role,
            "namespace": event.namespace,
            "knowledge_type": event.knowledge_type,
            "knowledge_tags": event.knowledge_tags,
            "source_ref": event.source_ref,
            "version_tag": event.version_tag,
            "visibility": event.visibility,
            "governance_source": event.governance_source,
            "review_status": event.review_status,
            "reviewed_by": event.reviewed_by,
            "reviewed_at": event.reviewed_at.isoformat() if event.reviewed_at is not None else None,
            "review_note": event.review_note,
            "status": "deleted" if event.deleted_at is not None else "active",
            "created_at": event.created_at.isoformat(),
            "deleted_at": event.deleted_at.isoformat() if event.deleted_at is not None else None,
        }

    def _load_knowledge_events(
        memory_service: MemoryService,
        *,
        lifecycle_status: Literal["active", "deleted", "all"] = "active",
        query: str | None = None,
    ) -> list[MemoryEvent]:
        repository = memory_service.repository
        if repository is None:
            return []
        return repository.list_recent(
            limit=100000,
            status=lifecycle_status,
            namespace="knowledge",
            query=query,
        )

    def _load_knowledge_event_by_id(
        memory_service: MemoryService,
        knowledge_id: str,
    ) -> MemoryEvent | None:
        events = _load_knowledge_events(memory_service, lifecycle_status="all")
        for event in events:
            if event.entry_id == knowledge_id:
                return event
        return None

    def _event_datetime_for_sort(event: MemoryEvent, sort_by: str) -> datetime | None:
        candidate = event.reviewed_at if sort_by == "reviewed_at" else event.created_at
        if candidate is None:
            return None
        if candidate.tzinfo is None:
            return candidate.replace(tzinfo=timezone.utc)
        return candidate.astimezone(timezone.utc)

    def _event_sort_key(event: MemoryEvent, sort_by: str) -> tuple[float, str]:
        event_dt = _event_datetime_for_sort(event, sort_by)
        timestamp = event_dt.timestamp() if event_dt is not None else missing_datetime_sort_value
        return timestamp, event.entry_id

    def _encode_cursor(*, sort_by: str, sort_order: str, event: MemoryEvent) -> str:
        primary, event_id = _event_sort_key(event, sort_by)
        payload = {
            "v": 1,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "primary": primary,
            "entry_id": event_id,
        }
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _decode_cursor_or_raise(*, cursor: str, sort_by: str, sort_order: str) -> tuple[float, str]:
        try:
            padded_cursor = cursor + ("=" * (-len(cursor) % 4))
            payload = json.loads(base64.urlsafe_b64decode(padded_cursor).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid cursor") from exc

        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if payload.get("sort_by") != sort_by or payload.get("sort_order") != sort_order:
            raise HTTPException(status_code=400, detail="cursor sort settings mismatch")

        entry_id = str(payload.get("entry_id", "")).strip()
        if not entry_id:
            raise HTTPException(status_code=400, detail="invalid cursor")
        try:
            primary = float(payload.get("primary"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid cursor") from exc
        return primary, entry_id

    def _validate_review_request_or_raise(*, decision: str, review_note: str | None) -> str | None:
        normalized_note = review_note.strip() if isinstance(review_note, str) else None
        if decision == "reject" and not normalized_note:
            raise HTTPException(status_code=400, detail="review_note is required when decision=reject")
        return normalized_note or None

    @router.get("/knowledge/items")
    def list_knowledge_items(
        limit: int = Query(default=30, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        cursor: str | None = Query(default=None),
        sort_by: Literal["created_at", "reviewed_at"] = Query(default="created_at"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
        review_status: Literal["pending_review", "approved", "rejected"] | None = None,
        status: Literal["active", "deleted", "all"] = Query(default="active"),
        q: str | None = Query(default=None),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        if cursor and offset > 0:
            raise HTTPException(status_code=400, detail="cursor and offset cannot be used together")

        events = _load_knowledge_events(memory_service, lifecycle_status=status, query=q)
        if review_status is not None:
            events = [event for event in events if event.review_status == review_status]

        descending = sort_order == "desc"
        sorted_events = sorted(events, key=lambda event: _event_sort_key(event, sort_by), reverse=descending)

        if cursor:
            cursor_key = _decode_cursor_or_raise(cursor=cursor, sort_by=sort_by, sort_order=sort_order)
            if descending:
                sorted_events = [event for event in sorted_events if _event_sort_key(event, sort_by) < cursor_key]
            else:
                sorted_events = [event for event in sorted_events if _event_sort_key(event, sort_by) > cursor_key]
            effective_offset = 0
        else:
            effective_offset = offset

        paged_events = sorted_events[effective_offset : effective_offset + limit]
        has_more = len(sorted_events) > (effective_offset + len(paged_events))
        next_cursor = (
            _encode_cursor(sort_by=sort_by, sort_order=sort_order, event=paged_events[-1])
            if has_more and paged_events
            else None
        )
        next_offset = (
            (effective_offset + len(paged_events))
            if (not cursor and has_more)
            else None
        )
        return {
            "items": [_serialize_event(event) for event in paged_events],
            "total_count": len(events),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "next_cursor": next_cursor,
            "next_offset": next_offset,
        }

    @router.get("/knowledge/summary")
    def get_knowledge_summary(
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        events = _load_knowledge_events(memory_service, lifecycle_status="all")
        by_review_status: dict[str, int] = {"pending_review": 0, "approved": 0, "rejected": 0}
        by_kind: dict[str, int] = {}
        active_count = 0
        deleted_count = 0
        for event in events:
            by_review_status[event.review_status] = by_review_status.get(event.review_status, 0) + 1
            by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
            if event.deleted_at is None:
                active_count += 1
            else:
                deleted_count += 1
        return {
            "total_count": len(events),
            "active_count": active_count,
            "deleted_count": deleted_count,
            "by_review_status": by_review_status,
            "by_kind": by_kind,
        }

    @router.post("/knowledge/items")
    def create_knowledge_item(
        request: KnowledgeCreateRequest,
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        repository = memory_service.repository
        if repository is None:
            raise HTTPException(status_code=503, detail="knowledge repository unavailable")

        now = datetime.now(timezone.utc)
        event = MemoryEvent(
            kind=request.kind.value,
            content=request.content,
            role=request.role,
            namespace="knowledge",
            knowledge_type=request.knowledge_type,
            knowledge_tags=request.knowledge_tags,
            source_ref=request.source_ref,
            version_tag=request.version_tag or "v1",
            visibility=request.visibility,
            source_context="manual:knowledge_panel",
            governance_source="manual",
            review_status="approved",
            reviewed_by=request.reviewer,
            reviewed_at=now,
            review_note=request.review_note,
            created_at=now,
        )
        repository.save_event(event)
        return {"success": True, "item": _serialize_event(event)}

    @router.post("/knowledge/items/{knowledge_id}/review")
    def review_knowledge_item(
        knowledge_id: str,
        request: KnowledgeReviewRequest,
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        repository = memory_service.repository
        if repository is None:
            raise HTTPException(status_code=503, detail="knowledge repository unavailable")

        existing = _load_knowledge_event_by_id(memory_service, knowledge_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="knowledge item not found")

        normalized_review_note = _validate_review_request_or_raise(
            decision=request.decision,
            review_note=request.review_note,
        )

        decision_map = {
            "approve": "approved",
            "reject": "rejected",
            "pend": "pending_review",
        }
        next_status = decision_map[request.decision]
        reviewed_at = datetime.now(timezone.utc) if next_status in {"approved", "rejected"} else None

        updated = repository.update_event(
            knowledge_id,
            review_status=next_status,
            reviewed_by=request.reviewer,
            reviewed_at=reviewed_at,
            review_note=normalized_review_note,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="knowledge item not found")

        latest = _load_knowledge_event_by_id(memory_service, knowledge_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="knowledge item not found")

        return {"success": True, "item": _serialize_event(latest)}

    @router.post("/knowledge/items/review-batch")
    def review_knowledge_items_batch(
        request: KnowledgeBatchReviewRequest,
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        repository = memory_service.repository
        if repository is None:
            raise HTTPException(status_code=503, detail="knowledge repository unavailable")

        normalized_review_note = _validate_review_request_or_raise(
            decision=request.decision,
            review_note=request.review_note,
        )

        normalized_ids: list[str] = []
        seen: set[str] = set()
        for knowledge_id in request.knowledge_ids:
            normalized_id = knowledge_id.strip()
            if not normalized_id or normalized_id in seen:
                continue
            seen.add(normalized_id)
            normalized_ids.append(normalized_id)

        if not normalized_ids:
            return {
                "success": True,
                "decision": request.decision,
                "updated": 0,
                "failed": 0,
                "updated_ids": [],
                "failed_ids": [],
            }

        decision_map = {
            "approve": "approved",
            "reject": "rejected",
            "pend": "pending_review",
        }
        next_status = decision_map[request.decision]
        reviewed_at = datetime.now(timezone.utc) if next_status in {"approved", "rejected"} else None

        updated_ids: list[str] = []
        failed_ids: list[str] = []
        for knowledge_id in normalized_ids:
            existing = _load_knowledge_event_by_id(memory_service, knowledge_id)
            if existing is None:
                failed_ids.append(knowledge_id)
                continue

            updated = repository.update_event(
                knowledge_id,
                review_status=next_status,
                reviewed_by=request.reviewer,
                reviewed_at=reviewed_at,
                review_note=normalized_review_note,
            )
            if updated:
                updated_ids.append(knowledge_id)
            else:
                failed_ids.append(knowledge_id)

        return {
            "success": len(failed_ids) == 0,
            "decision": request.decision,
            "updated": len(updated_ids),
            "failed": len(failed_ids),
            "updated_ids": updated_ids,
            "failed_ids": failed_ids,
        }

    return router
