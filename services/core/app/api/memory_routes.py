from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_memory_service
from app.memory.models import MemoryEmotion, MemoryKind, MemoryStrength
from app.memory.service import MemoryService


class MemoryCreateRequest(BaseModel):
    kind: MemoryKind
    content: str
    role: str | None = None
    strength: MemoryStrength = MemoryStrength.NORMAL
    importance: int = 5
    emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL
    keywords: list[str] | None = None
    subject: str | None = None


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    kind: MemoryKind | None = None
    importance: int | None = Field(default=None, ge=0, le=10)
    strength: MemoryStrength | None = None
    emotion_tag: MemoryEmotion | None = None
    keywords: list[str] | None = None
    subject: str | None = None


class MemoryBatchDeleteRequest(BaseModel):
    memory_ids: list[str]


def build_memory_router() -> APIRouter:
    router = APIRouter()

    @router.get("/memory/summary")
    def get_memory_summary(memory_service: MemoryService = Depends(get_memory_service)) -> dict:
        return memory_service.get_memory_summary()

    @router.get("/memory/relationship-summary")
    def get_relationship_summary(memory_service: MemoryService = Depends(get_memory_service)) -> dict:
        return memory_service.get_relationship_summary()

    @router.get("/memory/timeline")
    def get_memory_timeline(
        limit: int = 30,
        status: Literal["active", "deleted", "all"] = Query(default="active"),
        kind: MemoryKind | None = None,
        namespace: str | None = None,
        visibility: Literal["internal", "user"] | None = None,
        q: str | None = Query(default=None),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        kinds = [kind] if kind is not None else None
        collection = memory_service.list_recent(
            limit=limit,
            kinds=kinds,
            status=status,
            namespace=namespace,
            visibility=visibility,
            query=q,
        )
        return {
            "entries": [entry.to_display_dict() for entry in collection.entries],
            "total_count": collection.total_count,
            "query_summary": collection.query_summary,
        }

    @router.get("/memory/search")
    def search_memories(q: str, limit: int = 10, memory_service: MemoryService = Depends(get_memory_service)) -> dict:
        result = memory_service.search(q, limit=limit)
        return {
            "entries": [e.to_display_dict() for e in result.entries],
            "total_count": result.total_count,
            "query_summary": result.query_summary,
        }

    @router.post("/memory")
    def create_memory(request: MemoryCreateRequest, memory_service: MemoryService = Depends(get_memory_service)) -> dict:
        entry = memory_service.create(
            kind=request.kind,
            content=request.content,
            role=request.role,
            strength=request.strength,
            importance=request.importance,
            emotion_tag=request.emotion_tag,
            keywords=request.keywords,
            subject=request.subject,
            source_context="手动创建",
        )
        return {"success": True, "entry": entry.to_display_dict()}

    @router.delete("/memory/{memory_id}")
    def delete_memory(
        memory_id: str,
        hard: bool = Query(default=False),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        success = memory_service.purge(memory_id) if hard else memory_service.delete(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return {"success": True, "deleted_id": memory_id, "mode": "hard" if hard else "soft"}

    @router.post("/memory/batch-delete")
    def batch_delete_memories(
        request: MemoryBatchDeleteRequest,
        hard: bool = Query(default=False),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> dict:
        if not request.memory_ids:
            return {"success": True, "deleted": 0, "failed": 0}
        result = memory_service.delete_many(request.memory_ids, hard=hard)
        return {
            "success": result["failed"] == 0,
            "deleted": result["deleted"],
            "failed": result["failed"],
            "total": len(request.memory_ids),
            "mode": "hard" if hard else "soft",
        }

    @router.post("/memory/{memory_id}/restore")
    def restore_memory(memory_id: str, memory_service: MemoryService = Depends(get_memory_service)) -> dict:
        success = memory_service.restore(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return {"success": True, "restored_id": memory_id}

    @router.get("/memory/observability")
    def get_memory_observability(request: Request) -> dict:
        tracker = getattr(request.app.state, "memory_observability_tracker", None)
        if tracker is None or not hasattr(tracker, "snapshot"):
            return {
                "window": {"max_samples": 0, "updated_at": None},
                "latency": {
                    "retrieval_ms": {"count": 0, "avg": None, "p50": None, "p95": None},
                    "chat_ms": {"count": 0, "avg": None, "p50": None, "p95": None},
                },
                "quality": {
                    "queries": 0,
                    "failures": 0,
                    "hit_queries": 0,
                    "hit_rate": None,
                    "avg_hits_per_query": None,
                    "avg_similarity": None,
                },
                "write": {
                    "attempts": 0,
                    "failures": 0,
                    "failure_rate": None,
                },
                "alerts": [],
                "thresholds": {
                    "retrieval_p95_ms": 120.0,
                    "chat_p95_ms": 1500.0,
                    "write_failure_rate": 0.01,
                    "retrieval_hit_rate": 0.4,
                    "min_latency_samples_for_alert": 20,
                    "min_write_samples_for_alert": 20,
                    "min_quality_samples_for_alert": 20,
                },
            }
        return tracker.snapshot()

    @router.post("/memory/observability/reset")
    def reset_memory_observability(request: Request) -> dict:
        tracker = getattr(request.app.state, "memory_observability_tracker", None)
        if tracker is None or not hasattr(tracker, "reset"):
            return {"success": True, "reset": False, "reason": "tracker_unavailable"}
        tracker.reset()
        return {"success": True, "reset": True}

    @router.put("/memory/{memory_id}")
    def update_memory(
        memory_id: str, request: MemoryUpdateRequest, memory_service: MemoryService = Depends(get_memory_service)
    ) -> dict:
        success = memory_service.update(
            memory_id,
            content=request.content,
            kind=request.kind,
            importance=request.importance,
            strength=request.strength,
            emotion_tag=request.emotion_tag,
            keywords=request.keywords,
            subject=request.subject,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        entry = memory_service.get_by_id(memory_id)
        return {"success": True, "entry": entry.to_display_dict() if entry else None}

    @router.post("/memory/{memory_id}/star")
    def star_memory(
        memory_id: str, important: bool = True, memory_service: MemoryService = Depends(get_memory_service)
    ) -> dict:
        success = memory_service.star(memory_id, important=important)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return {"success": True, "starred": important, "memory_id": memory_id}

    return router
