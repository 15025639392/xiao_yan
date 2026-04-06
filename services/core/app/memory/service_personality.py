from __future__ import annotations

from typing import TYPE_CHECKING

from app.memory.models import MemoryEmotion, MemoryEntry, MemoryKind, MemoryStrength

if TYPE_CHECKING:
    from app.memory.service import MemoryService


class MemoryPersonalityMixin:
    def _adjust_strength_for_personality(
        self: "MemoryService",
        kind: MemoryKind,
        base_strength: MemoryStrength,
    ) -> MemoryStrength:
        """Adjust initial memory strength based on personality dimensions."""
        p = self.personality

        match kind:
            case MemoryKind.FACT:
                if p.openness >= 70:
                    return self._boost_strength(base_strength)
            case MemoryKind.EPISODIC:
                if p.agreeableness >= 70:
                    return self._boost_strength(base_strength)
            case MemoryKind.EMOTIONAL:
                if p.neuroticism >= 60:
                    return self._boost_strength(base_strength)
                if p.neuroticism <= 30:
                    return self._weaken_strength(base_strength)

        return base_strength

    def _rank_by_personality(
        self: "MemoryService",
        entries: list[MemoryEntry],
        query: str,  # noqa: ARG002 - reserved for future relevance tuning
    ) -> list[MemoryEntry]:
        """Re-rank entries with personality-aware bias."""
        p = self.personality

        def score(entry: MemoryEntry) -> float:
            base = entry.retention_score

            if p.openness >= 70 and entry.kind in (MemoryKind.FACT, MemoryKind.SEMANTIC):
                base += 0.1
            if p.extraversion >= 70 and entry.kind == MemoryKind.EPISODIC:
                base += 0.1
            if p.neuroticism >= 60 and entry.emotion_tag == MemoryEmotion.NEGATIVE:
                base += 0.15
            if p.agreeableness >= 70 and entry.emotion_tag == MemoryEmotion.POSITIVE:
                base += 0.08

            return base

        return sorted(entries, key=score, reverse=True)

    def _extract_keywords(self: "MemoryService", text: str) -> list[str]:
        """Simple Chinese+English keyword extraction."""
        import re

        cjk_words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
        en_words = re.findall(r"[A-Za-z]{3,}", text.lower())
        return list(set(cjk_words[:10] + en_words[:5]))

    @staticmethod
    def _boost_strength(strength: MemoryStrength) -> MemoryStrength:
        """Increase one level."""
        order = [
            MemoryStrength.FAINT,
            MemoryStrength.WEAK,
            MemoryStrength.NORMAL,
            MemoryStrength.VIVID,
            MemoryStrength.CORE,
        ]
        try:
            idx = order.index(strength)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return strength

    @staticmethod
    def _weaken_strength(strength: MemoryStrength) -> MemoryStrength:
        """Decrease one level."""
        order = [
            MemoryStrength.FAINT,
            MemoryStrength.WEAK,
            MemoryStrength.NORMAL,
            MemoryStrength.VIVID,
            MemoryStrength.CORE,
        ]
        try:
            idx = order.index(strength)
            if idx > 0:
                return order[idx - 1]
        except ValueError:
            pass
        return strength

