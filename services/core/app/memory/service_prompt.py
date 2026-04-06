from __future__ import annotations

from typing import TYPE_CHECKING

from app.memory.models import MemoryCollection, MemoryKind, MemoryStrength

if TYPE_CHECKING:
    from app.memory.service import MemoryService


class MemoryPromptMixin:
    def build_memory_prompt_context(
        self: "MemoryService",
        user_message: str | None = None,
        max_chars: int = 800,
    ) -> str:
        parts: list[str] = []

        if user_message and self.repository:
            relevant = self.search(user_message, limit=5)
            if relevant.entries:
                context = relevant.to_prompt_context(max_chars=max_chars // 2)
                if context:
                    parts.append(context)

        recent = self.list_recent(limit=20)
        important_entries = [
            e
            for e in recent.entries
            if e.kind in (MemoryKind.FACT, MemoryKind.EPISODIC) and e.importance >= 6
        ][:5]

        if important_entries:
            fact_collection = MemoryCollection(entries=important_entries)
            facts_context = fact_collection.to_prompt_context(max_chars=max_chars // 2)
            if facts_context:
                parts.append(facts_context)

        if not parts:
            return ""

        return "【你记得的事情】\n" + "\n".join(parts)

    def get_memory_summary(self: "MemoryService") -> dict:
        if self.repository is None:
            return {
                "total_estimated": 0,
                "by_kind": {},
                "recent_count": 0,
                "strong_memories": 0,
                "available": False,
            }

        recent = self.list_recent(limit=200)
        by_kind: dict[str, int] = {}
        strong = 0

        for entry in recent.entries:
            k = entry.kind.value
            by_kind[k] = by_kind.get(k, 0) + 1
            if entry.strength in (MemoryStrength.VIVID, MemoryStrength.CORE):
                strong += 1

        return {
            "total_estimated": recent.total_count,
            "by_kind": by_kind,
            "recent_count": len(recent.entries),
            "strong_memories": strong,
            "available": True,
        }

    def get_memory_timeline(self: "MemoryService", limit: int = 30) -> list[dict]:
        recent = self.list_recent(limit=limit)
        return [entry.to_display_dict() for entry in recent.entries]

