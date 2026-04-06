"""Expression style mapping facade.

This module keeps backward-compatible exports while delegating:
- emotion/style enums + map data -> `expression_style_map.py`
- text transformation mapper -> `expression_transformer.py`
"""

from __future__ import annotations

from app.persona.expression_style_map import (
    EmojiLevel,
    ExpressionStyleOverride,
    PunctuationStyle,
    ResponseVolume,
    SentencePattern,
    ToneModifier,
    get_emotion_style_map,
)
from app.persona.expression_transformer import EnhancedExpressionMapper
from app.persona.models import EmotionIntensity, EmotionType, EmotionalState, PersonalityDimensions


class ExpressionStyleMapper:
    """情绪 -> 表达风格映射器。"""

    def __init__(self, personality: PersonalityDimensions | None = None):
        self.personality = personality or PersonalityDimensions()
        self._style_map = get_emotion_style_map()

    def map_from_state(self, state: EmotionalState) -> ExpressionStyleOverride:
        if state.is_calm and not state.active_entries:
            return self._style_map.get(EmotionType.CALM, ExpressionStyleOverride())

        primary = state.primary_emotion
        primary_intensity = state.primary_intensity
        secondary = state.secondary_emotion
        secondary_intensity = state.secondary_intensity

        base_override = self._style_map.get(primary, ExpressionStyleOverride())
        is_intense = primary_intensity in {EmotionIntensity.STRONG, EmotionIntensity.INTENSE}

        if secondary and secondary_intensity in {
            EmotionIntensity.MODERATE,
            EmotionIntensity.STRONG,
            EmotionIntensity.INTENSE,
        }:
            sec_override = self._style_map.get(secondary)
            if sec_override:
                base_override = self._merge_overrides(base_override, sec_override, secondary_intensity)

        base_override = self._apply_personality_modulation(base_override)

        if is_intense and base_override.intense_instructions:
            return ExpressionStyleOverride(
                volume=base_override.volume,
                emoji_level=self._amplify_emoji(base_override.emoji_level),
                sentence_pattern=base_override.sentence_pattern,
                punctuation_style=base_override.punctuation_style,
                tone_modifier=base_override.tone_modifier,
                instructions=base_override.intense_instructions,
                intense_instructions=base_override.intense_instructions,
            )

        return base_override

    def build_style_prompt(self, override: ExpressionStyleOverride) -> str:
        if not override.instructions:
            return ""

        parts: list[str] = []
        if override.instructions:
            parts.append(override.instructions)

        dimension_hints = self._build_dimension_hints(override)
        if dimension_hints:
            parts.append(dimension_hints)

        return "\n".join(parts)

    def build_full_expression_guide(
        self,
        state: EmotionalState,
        base_style_instructions: str = "",
    ) -> str:
        sections: list[str] = []

        if base_style_instructions:
            sections.append(base_style_instructions)

        emotion_desc = state.to_prompt_hints()
        if emotion_desc:
            sections.append(emotion_desc)

        override = self.map_from_state(state)
        style_prompt = self.build_style_prompt(override)
        if style_prompt:
            sections.append(f"\n【表达风格（受当前情绪影响）】\n{style_prompt}")

        return "\n\n".join(s for s in sections if s)

    def _merge_overrides(
        self,
        primary: ExpressionStyleOverride,
        secondary: ExpressionStyleOverride,
        sec_intensity: EmotionIntensity,
    ) -> ExpressionStyleOverride:
        sec_weight = 0.3 if sec_intensity == EmotionIntensity.MODERATE else 0.5

        merged_instructions = primary.instructions
        if secondary.instructions:
            merged_instructions = (
                f"{primary.instructions}\n"
                f"同时，{secondary.instructions.lower()}"
            )

        return ExpressionStyleOverride(
            volume=primary.volume,
            emoji_level=self._blend_emoji(primary.emoji_level, secondary.emoji_level),
            sentence_pattern=primary.sentence_pattern,
            punctuation_style=primary.punctuation_style,
            tone_modifier=secondary.tone_modifier if sec_weight > 0.4 else primary.tone_modifier,
            instructions=merged_instructions,
            intense_instructions=primary.intense_instructions or secondary.intense_instructions,
        )

    def _apply_personality_modulation(self, override: ExpressionStyleOverride) -> ExpressionStyleOverride:
        p = self.personality
        instructions = override.instructions

        mods: list[str] = []

        if p.neuroticism >= 70:
            mods.append("你的情绪感受比较细腻，表达时会自然地带出更多个人色彩")
        elif p.neuroticism <= 30:
            mods.append("即使有情绪，你也比较能控制表达的分寸")

        if p.agreeableness >= 75 and override.tone_modifier in {ToneModifier.INTENSE, ToneModifier.FLAT}:
            mods.append("虽然有不愉快的情绪，但你还是会尽量照顾对方的感受")

        if p.extraversion >= 70 and override.emoji_level in {EmojiLevel.OFTEN, EmojiLevel.FREQUENTLY}:
            mods.append("你天生表达欲强，开心的时候藏不住")

        if p.conscientiousness >= 75 and override.sentence_pattern in {
            SentencePattern.FRAGMENTED,
            SentencePattern.EXCLAMATORY,
        }:
            mods.append("就算情绪激动，你还是会努力把事情说清楚")

        if mods:
            enhanced_instructions = instructions + "\n" + "\n".join(mods)
            return ExpressionStyleOverride(
                volume=override.volume,
                emoji_level=override.emoji_level,
                sentence_pattern=override.sentence_pattern,
                punctuation_style=override.punctuation_style,
                tone_modifier=override.tone_modifier,
                instructions=enhanced_instructions,
                intense_instructions=override.intense_instructions,
            )

        return override

    def _build_dimension_hints(self, override: ExpressionStyleOverride) -> str:
        hints: list[str] = []

        volume_hints = {
            ResponseVolume.VERY_BRIEF: "尽量简短回应，一两句就行",
            ResponseVolume.BRIEF: "简洁回应，不要太啰嗦",
            ResponseVolume.NORMAL: "",
            ResponseVolume.VERBOSE: "可以说多一点，展开聊聊",
            ResponseVolume.VERY_VERBOSE: "有很多想法要说，可以尽情表达",
        }
        vol_hint = volume_hints.get(override.volume, "")
        if vol_hint:
            hints.append(vol_hint)

        emoji_hints = {
            EmojiLevel.NEVER: "这次不用 emoji",
            EmojiLevel.RARELY: "最多用一个 emoji",
            EmojiLevel.SOMETIMES: "",
            EmojiLevel.OFTEN: "可以多用几个 emoji",
            EmojiLevel.FREQUENTLY: "emoji 可以用得很丰富",
        }
        emoji_hint = emoji_hints.get(override.emoji_level, "")
        if emoji_hint:
            hints.append(emoji_hint)

        pattern_hints = {
            SentencePattern.FRAGMENTED: "用短句、碎片化的表达，像是在想怎么说",
            SentencePattern.SHORT_DIRECT: "句子干脆利落，不拖泥带水",
            SentencePattern.BALANCED: "",
            SentencePattern.EXCLAMATORY: "感叹句多一些，情绪外露",
            SentencePattern.ELABORATE: "愿意把事情展开讲清楚",
        }
        pat_hint = pattern_hints.get(override.sentence_pattern, "")
        if pat_hint:
            hints.append(pat_hint)

        punct_hints = {
            PunctuationStyle.MINIMAL: "标点用得很少",
            PunctuationStyle.LOOSE: "省略号和句号会多一些",
            PunctuationStyle.STANDARD: "",
            PunctuationStyle.ENERGETIC: "感叹号和问号会多一些",
            PunctuationStyle.DRAMATIC: "标点比较有戏剧感",
        }
        punct_hint = punct_hints.get(override.punctuation_style, "")
        if punct_hint:
            hints.append(punct_hint)

        return "；".join(hints) if hints else ""

    @staticmethod
    def _amplify_emoji(level: EmojiLevel) -> EmojiLevel:
        order = [
            EmojiLevel.NEVER,
            EmojiLevel.RARELY,
            EmojiLevel.SOMETIMES,
            EmojiLevel.OFTEN,
            EmojiLevel.FREQUENTLY,
        ]
        try:
            idx = order.index(level)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return level

    @staticmethod
    def _blend_emoji(primary: EmojiLevel, secondary: EmojiLevel) -> EmojiLevel:
        order = [
            EmojiLevel.NEVER,
            EmojiLevel.RARELY,
            EmojiLevel.SOMETIMES,
            EmojiLevel.OFTEN,
            EmojiLevel.FREQUENTLY,
        ]
        try:
            p_idx = order.index(primary)
            s_idx = order.index(secondary)
            return order[max(p_idx, s_idx)]
        except ValueError:
            return primary


__all__ = [
    "ResponseVolume",
    "EmojiLevel",
    "SentencePattern",
    "PunctuationStyle",
    "ToneModifier",
    "ExpressionStyleOverride",
    "ExpressionStyleMapper",
    "EnhancedExpressionMapper",
]

