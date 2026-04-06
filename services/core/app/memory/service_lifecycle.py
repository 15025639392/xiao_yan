from __future__ import annotations

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING

from app.memory.models import MemoryCollection, MemoryEmotion, MemoryEntry, MemoryKind, MemoryStrength

if TYPE_CHECKING:
    from app.memory.service import MemoryService

logger = getLogger(__name__)


class MemoryLifecycleMixin:
    def strengthen(self: "MemoryService", memory_id: str) -> bool:
        logger.debug("Strengthening memory %s", memory_id)
        return True

    def weaken_old_memories(self: "MemoryService", days_threshold: int = 30) -> int:
        if self.repository is None:
            return 0

        cutoff = datetime.now(timezone.utc).timestamp() - (days_threshold * 86400)
        events = self.repository.list_recent(limit=1000)
        old_count = sum(1 for e in events if e.created_at.timestamp() < cutoff)

        if old_count > 0:
            logger.info("Found %d memories older than %d days (conceptual decay)", old_count, days_threshold)

        return old_count

    def search_context(
        self: "MemoryService",
        query: str,
        context_type: str = "all",
        limit: int = 10,
    ) -> MemoryCollection:
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        events = self.repository.search_relevant(query, limit=limit * 2)
        entries = [e.to_entry() for e in events]

        if context_type == "conversation":
            entries = [e for e in entries if e.kind == MemoryKind.EPISODIC]
        elif context_type == "preferences":
            entries = [e for e in entries if "偏好" in e.content or "习惯" in e.content]

        entries.sort(
            key=lambda e: (self._importance_score(e), e.created_at),
            reverse=True,
        )

        return MemoryCollection(
            entries=entries[:limit],
            total_count=len(entries),
            query_summary=f"搜索「{query[:20]}」的{context_type}上下文",
        )

    def get_conversation_history(
        self: "MemoryService",
        days: int = 7,
        emotion_filter: MemoryEmotion | None = None,
    ) -> MemoryCollection:
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        events = self.repository.list_recent(limit=1000)
        entries = [e.to_entry() for e in events]

        entries = [e for e in entries if e.created_at >= cutoff_date]
        if emotion_filter:
            entries = [e for e in entries if e.emotion_tag == emotion_filter]

        entries = [e for e in entries if e.kind == MemoryKind.EPISODIC]

        return MemoryCollection(
            entries=entries[:50],
            total_count=len(entries),
            query_summary=f"最近{days}天的对话历史",
        )

    def _importance_score(self: "MemoryService", entry: MemoryEntry) -> int:
        score = 0

        if entry.strength == MemoryStrength.CORE:
            score += 5
        elif entry.strength == MemoryStrength.VIVID:
            score += 3
        elif entry.strength == MemoryStrength.NORMAL:
            score += 2
        elif entry.strength == MemoryStrength.WEAK:
            score += 1

        if entry.emotion_tag in [MemoryEmotion.POSITIVE, MemoryEmotion.NEGATIVE]:
            score += 2

        if len(entry.related_memory_ids) > 3:
            score += 1

        score += min(entry.importance, 10)

        return min(score, 10)

    def apply_time_decay(self: "MemoryService") -> int:
        if self.repository is None:
            return 0

        events = self.repository.list_recent(limit=10000)
        decayed_count = 0
        current_time = datetime.now(timezone.utc)

        for event in events:
            entry = event.to_entry()
            age_days = (current_time - entry.created_at).total_seconds() / 86400
            new_strength = self._calculate_decay(entry.strength, age_days)

            if new_strength != entry.strength:
                self.repository.update_event(
                    event.entry_id,
                    strength=new_strength.value,
                )
                decayed_count += 1

        if decayed_count > 0:
            logger.info("Applied time decay to %d memories", decayed_count)

        return decayed_count

    def _calculate_decay(
        self: "MemoryService",
        current_strength: MemoryStrength,
        age_days: float,
    ) -> MemoryStrength:
        if age_days < 7:
            return current_strength
        if age_days < 30:
            if current_strength == MemoryStrength.CORE:
                return MemoryStrength.VIVID
            if current_strength == MemoryStrength.VIVID:
                return MemoryStrength.NORMAL
            if current_strength == MemoryStrength.NORMAL:
                return MemoryStrength.WEAK
        elif age_days < 90:
            if current_strength == MemoryStrength.VIVID:
                return MemoryStrength.NORMAL
            if current_strength == MemoryStrength.NORMAL:
                return MemoryStrength.WEAK
            if current_strength == MemoryStrength.WEAK:
                return MemoryStrength.FAINT
        else:
            return MemoryStrength.FAINT

        return current_strength

    def cleanup_old_memories(self: "MemoryService", max_age_days: int = 365) -> int:
        if self.repository is None:
            return 0

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        events = self.repository.list_recent(limit=10000)

        deleted_count = 0
        for event in events:
            entry = event.to_entry()
            if entry.created_at < cutoff_date and entry.strength == MemoryStrength.FAINT:
                if self.repository.delete_event(event.entry_id):
                    deleted_count += 1

        if deleted_count > 0:
            logger.info("Cleaned up %d old memories", deleted_count)

        return deleted_count

