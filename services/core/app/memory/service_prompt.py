from __future__ import annotations

from typing import TYPE_CHECKING

from app.memory.models import MemoryCollection, MemoryKind, MemoryStrength
from app.persona.models import PersonaValues

if TYPE_CHECKING:
    from app.memory.service import MemoryService


class MemoryPromptMixin:
    def build_memory_prompt_context(
        self: "MemoryService",
        user_message: str | None = None,
        max_chars: int = 800,
        persona_values: PersonaValues | None = None,
    ) -> str:
        parts: list[str] = []
        relevant_entries = []

        if user_message and self.repository:
            relevant = self.search(user_message, limit=5)
            relevant_entries = relevant.entries
            if relevant.entries:
                context = relevant.to_prompt_context(max_chars=max_chars // 2)
                if context:
                    parts.append(context)

        recent = self.list_recent(limit=20)
        relationship_summary_context = self._build_relationship_summary_context(
            recent_entries=recent.entries,
            max_chars=max_chars // 4,
        )
        if relationship_summary_context:
            parts.insert(0, relationship_summary_context)

        continuity_context = self._build_relationship_continuity_context(
            relevant_entries=relevant_entries,
            recent_entries=recent.entries,
            max_chars=max_chars // 3,
            persona_values=persona_values,
        )
        if continuity_context:
            parts.insert(0, continuity_context)

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

    def _build_relationship_summary_context(
        self: "MemoryService",
        *,
        recent_entries,
        max_chars: int,
    ) -> str:
        summary = self._relationship_summary_from_entries(recent_entries)
        if not summary["available"]:
            return ""

        lines: list[str] = ["【关系状态摘要】"]
        if summary["boundaries"]:
            lines.append("相处边界：" + "；".join(summary["boundaries"]))
        if summary["commitments"]:
            lines.append("对用户承诺：" + "；".join(summary["commitments"]))
        if summary["preferences"]:
            lines.append("用户偏好：" + "；".join(summary["preferences"]))

        result = "\n".join(lines)
        return result[:max_chars] if len(result) > max_chars else result

    def _build_relationship_continuity_context(
        self: "MemoryService",
        *,
        relevant_entries,
        recent_entries,
        max_chars: int,
        persona_values: PersonaValues | None = None,
    ) -> str:
        continuity_entries = self._select_relationship_continuity_entries(relevant_entries, recent_entries)
        if not continuity_entries:
            return ""

        fragments: list[str] = []
        total_chars = 0
        for entry in continuity_entries:
            fragment = entry.to_prompt_fragment()
            if total_chars + len(fragment) + 1 > max_chars:
                break
            fragments.append(fragment)
            total_chars += len(fragment) + 1

        if not fragments:
            return ""

        principle_hint = ""
        if persona_values is not None:
            top_values = persona_values.to_core_principles_prompt()
            if top_values:
                principle_hint = f"基于你的价值底盘（{top_values}），"

        return (
            "【关系连续性】\n"
            f"{principle_hint}优先记住和对方边界、偏好、约定有关的事实：\n"
            + "\n".join(fragments)
        )

    def _select_relationship_continuity_entries(
        self: "MemoryService",
        relevant_entries,
        recent_entries,
    ):
        continuity_markers = (
            "喜欢", "不喜欢", "希望", "不想", "不要", "别",
            "先", "习惯", "边界", "答应", "约好", "约定", "承诺", "提醒",
        )
        merged_entries = []
        seen_ids: set[str] = set()

        for entry in list(relevant_entries) + list(recent_entries):
            if entry.id in seen_ids:
                continue
            if entry.kind not in (MemoryKind.FACT, MemoryKind.EPISODIC):
                continue
            if (
                entry.source_context not in {"value_signal:boundary", "value_signal:commitment"}
                and not any(marker in entry.content for marker in continuity_markers)
            ):
                continue
            seen_ids.add(entry.id)
            merged_entries.append(entry)

        merged_entries.sort(
            key=lambda entry: (entry.importance, entry.retention_score, entry.created_at),
            reverse=True,
        )
        return merged_entries[:4]

    def get_relationship_summary(self: "MemoryService") -> dict:
        if self.repository is None:
            return {
                "available": False,
                "boundaries": [],
                "commitments": [],
                "preferences": [],
            }

        recent = self.list_recent(limit=80)
        return self._relationship_summary_from_entries(recent.entries)

    def _relationship_summary_from_entries(self: "MemoryService", entries) -> dict:
        boundaries = self._collect_relationship_items(
            entries,
            matcher=lambda entry: entry.source_context == "value_signal:boundary" or entry.subject == "用户边界",
            prefixes=("用户边界：",),
        )
        commitments = self._collect_relationship_items(
            entries,
            matcher=lambda entry: entry.source_context == "value_signal:commitment" or entry.subject == "对用户承诺",
            prefixes=("承诺/计划：",),
        )
        preferences = self._collect_relationship_items(
            entries,
            matcher=lambda entry: entry.subject in {"用户偏好", "用户习惯"} or entry.content.startswith("用户偏好："),
            prefixes=("用户偏好：", "用户习惯："),
        )

        return {
            "available": bool(boundaries or commitments or preferences),
            "boundaries": boundaries,
            "commitments": commitments,
            "preferences": preferences,
        }

    def _collect_relationship_items(self: "MemoryService", entries, *, matcher, prefixes: tuple[str, ...]) -> list[str]:
        matched = [entry for entry in entries if matcher(entry)]
        matched.sort(
            key=lambda entry: (entry.importance, entry.retention_score, entry.created_at),
            reverse=True,
        )

        items: list[str] = []
        seen: set[str] = set()
        for entry in matched:
            content = entry.content
            for prefix in prefixes:
                if content.startswith(prefix):
                    content = content[len(prefix):]
                    break
            content = content.strip()
            if not content or content in seen:
                continue
            seen.add(content)
            items.append(content)
            if len(items) >= 3:
                break

        return items

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
            "relationship": self._relationship_summary_from_entries(recent.entries),
            "available": True,
        }

    def get_memory_timeline(self: "MemoryService", limit: int = 30) -> list[dict]:
        recent = self.list_recent(limit=limit)
        return [entry.to_display_dict() for entry in recent.entries]
