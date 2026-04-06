from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from app.memory.models import (
    MemoryCollection,
    MemoryEmotion,
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryStrength,
)

if TYPE_CHECKING:
    from app.memory.service import MemoryService

logger = getLogger(__name__)


class MemoryCRUDMixin:
    def save(self: "MemoryService", entry: MemoryEntry) -> MemoryEntry:
        if self.repository is not None:
            event = MemoryEvent.from_entry(entry)
            self.repository.save_event(event)
        return entry

    def create(
        self: "MemoryService",
        kind: MemoryKind,
        content: str,
        *,
        role: str | None = None,
        session_id: str | None = None,
        strength: MemoryStrength = MemoryStrength.NORMAL,
        importance: int = 5,
        emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL,
        keywords: list[str] | None = None,
        subject: str | None = None,
        source_context: str | None = None,
    ) -> MemoryEntry:
        entry = self._build_entry(
            kind=kind,
            content=content,
            role=role,
            session_id=session_id,
            strength=strength,
            importance=importance,
            emotion_tag=emotion_tag,
            keywords=keywords,
            subject=subject,
            source_context=source_context,
        )
        return self.save(entry)

    def _build_entry(
        self: "MemoryService",
        *,
        kind: MemoryKind,
        content: str,
        role: str | None = None,
        session_id: str | None = None,
        strength: MemoryStrength = MemoryStrength.NORMAL,
        importance: int = 5,
        emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL,
        keywords: list[str] | None = None,
        subject: str | None = None,
        source_context: str | None = None,
    ) -> MemoryEntry:
        return MemoryEntry(
            kind=kind,
            content=content,
            role=role,
            session_id=session_id,
            strength=self._adjust_strength_for_personality(kind, strength),
            importance=importance,
            emotion_tag=emotion_tag,
            keywords=keywords or self._extract_keywords(content),
            subject=subject,
            source_context=source_context,
        )

    def delete(self: "MemoryService", memory_id: str) -> bool:
        if self.repository is None:
            logger.warning("Cannot delete memory %s: no repository", memory_id)
            return False

        result = self.repository.delete_event(memory_id)
        if result:
            logger.info("Deleted memory %s", memory_id)
        else:
            logger.warning("Failed to delete memory %s: not found", memory_id)
        return result

    def delete_many(self: "MemoryService", memory_ids: list[str]) -> dict[str, int]:
        if self.repository is None:
            logger.warning("Cannot delete memories: no repository")
            return {"deleted": 0, "failed": len(memory_ids)}

        deleted_count = 0
        failed_count = 0

        for memory_id in memory_ids:
            if self.repository.delete_event(memory_id):
                deleted_count += 1
            else:
                failed_count += 1

        logger.info("Batch delete: %d succeeded, %d failed", deleted_count, failed_count)
        return {"deleted": deleted_count, "failed": failed_count}

    def update(
        self: "MemoryService",
        memory_id: str,
        *,
        content: str | None = None,
        kind: MemoryKind | None = None,
        importance: int | None = None,
        strength: MemoryStrength | None = None,
        emotion_tag: MemoryEmotion | None = None,
        keywords: list[str] | None = None,
        subject: str | None = None,
    ) -> bool:
        if self.repository is None:
            logger.warning("Cannot update memory %s: no repository", memory_id)
            return False

        update_kwargs: dict[str, object] = {}
        if content is not None:
            update_kwargs["content"] = content
            if keywords is None:
                update_kwargs.setdefault("keywords", self._extract_keywords(content))
        if kind is not None:
            update_kwargs["kind"] = kind.value
        if importance is not None:
            update_kwargs["importance"] = importance
        if strength is not None:
            update_kwargs["strength"] = strength.value
        if emotion_tag is not None:
            update_kwargs["emotion_tag"] = emotion_tag.value
        if keywords is not None:
            update_kwargs["keywords"] = keywords
        if subject is not None:
            update_kwargs["subject"] = subject

        if not update_kwargs:
            return True

        result = self.repository.update_event(memory_id, **update_kwargs)
        if result:
            logger.info("Updated memory %s with fields: %s", memory_id, list(update_kwargs.keys()))
        else:
            logger.warning("Failed to update memory %s: not found", memory_id)
        return result

    def star(self: "MemoryService", memory_id: str, important: bool = True) -> bool:
        new_importance = 9 if important else 5
        return self.update(memory_id, importance=new_importance)

    def get_by_id(self: "MemoryService", memory_id: str) -> MemoryEntry | None:
        if self.repository is None:
            return None
        recent = self.list_recent(limit=500)
        for entry in recent.entries:
            if entry.id == memory_id:
                return entry
        return None

    def list_recent(
        self: "MemoryService",
        limit: int = 20,
        kinds: list[MemoryKind] | None = None,
    ) -> MemoryCollection:
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        events = self.repository.list_recent(limit * 3)
        entries = [e.to_entry() for e in events]

        if kinds:
            entries = [e for e in entries if e.kind in kinds]

        entries.sort(key=lambda e: e.created_at, reverse=True)

        return MemoryCollection(
            entries=entries[:limit],
            total_count=len(entries),
            query_summary=f"最近 {limit} 条记录",
        )

    def search(
        self: "MemoryService",
        query: str,
        limit: int = 10,
        kinds: list[MemoryKind] | None = None,
    ) -> MemoryCollection:
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        events = self.repository.search_relevant(query, limit=limit * 3)
        entries = [e.to_entry() for e in events]

        if kinds:
            entries = [e for e in entries if e.kind in kinds]

        entries = self._rank_by_personality(entries, query)

        return MemoryCollection(
            entries=entries[:limit],
            total_count=len(entries),
            query_summary=f"搜索「{query[:20]}」的结果",
        )

