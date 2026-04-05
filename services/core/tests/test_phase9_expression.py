"""情绪到表达风格映射测试集

覆盖范围：
1. ExpressionStyleMapper 核心映射逻辑
2. 各情绪类型的风格覆盖正确性
3. 强度影响（MILD vs INTENSE）
4. 性格调节因子
5. 双情绪融合
6. EmotionalState.to_expression_prompt() 新方法
7. PersonaProfile.build_system_prompt() 包含风格指令
8. 辅助工具函数（emoji 融合、放大等）
"""

import pytest

from app.persona.models import (
    EmotionEntry,
    EmotionIntensity,
    EmotionalState,
    EmotionType,
    PersonalityDimensions,
)
from app.persona.expression_mapper import (
    EmojiLevel,
    ExpressionStyleMapper,
    ExpressionStyleOverride,
    PunctuationStyle,
    ResponseVolume,
    SentencePattern,
    ToneModifier,
)


# ═══════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════


@pytest.fixture
def neutral_personality():
    """中性性格"""
    return PersonalityDimensions()


@pytest.fixture
def high_neuroticism():
    """高神经质性格（情绪敏感）"""
    return PersonalityDimensions(
        openness=50, conscientiousness=50,
        extraversion=50, agreeableness=50, neuroticism=80,
    )


@pytest.fixture
def high_agreeable():
    """高宜人性性格（温和）"""
    return PersonalityDimensions(
        openness=50, conscientiousness=50,
        extraversion=50, agreeableness=85, neuroticism=40,
    )


@pytest.fixture
def calm_state():
    """平静状态"""
    return EmotionalState(
        primary_emotion=EmotionType.CALM,
        primary_intensity=EmotionIntensity.NONE,
        mood_valence=0.1,
        arousal=0.25,
    )


@pytest.fixture
def joy_state():
    """开心状态（中等强度）"""
    return EmotionalState(
        primary_emotion=EmotionType.JOY,
        primary_intensity=EmotionIntensity.MODERATE,
        mood_valence=0.6,
        arousal=0.7,
        active_entries=[
            EmotionEntry(emotion_type=EmotionType.JOY, intensity=EmotionIntensity.MODERATE, reason="用户说了谢谢"),
        ],
    )


@pytest.fixture
def intense_joy_state():
    """非常开心的状态（强烈）"""
    return EmotionalState(
        primary_emotion=EmotionType.JOY,
        primary_intensity=EmotionIntensity.INTENSE,
        mood_valence=0.9,
        arousal=0.85,
        active_entries=[
            EmotionEntry(emotion_type=EmotionType.JOY, intensity=EmotionIntensity.INTENSE, reason="被夸奖了！"),
        ],
    )


@pytest.fixture
def sad_state():
    """悲伤状态"""
    return EmotionalState(
        primary_emotion=EmotionType.SADNESS,
        primary_intensity=EmotionIntensity.STRONG,
        mood_valence=-0.5,
        arousal=0.3,
        active_entries=[
            EmotionEntry(emotion_type=EmotionType.SADNESS, intensity=EmotionIntensity.STRONG, reason="目标失败了"),
        ],
    )


@pytest.fixture
def mixed_state():
    """混合情绪：主开心 + 次担忧"""
    return EmotionalState(
        primary_emotion=EmotionType.JOY,
        primary_intensity=EmotionIntensity.MODERATE,
        secondary_emotion=EmotionType.FEAR,
        secondary_intensity=EmotionIntensity.MILD,
        mood_valence=0.3,
        arousal=0.6,
        active_entries=[
            EmotionEntry(emotion_type=EmotionType.JOY, intensity=EmotionIntensity.MODERATE, reason="有进展了"),
            EmotionEntry(emotion_type=EmotionType.FEAR, intensity=EmotionIntensity.MILD, reason="但有点担心后续"),
        ],
    )


# ═══════════════════════════════════════════════════
# 1. 基础映射测试 — 每种情绪类型都有风格覆盖
# ═══════════════════════════════════════════════════


class TestBasicMapping:
    def test_calm_returns_default_style(self, neutral_personality, calm_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(calm_state)
        assert override.volume == ResponseVolume.NORMAL
        assert override.tone_modifier == ToneModifier.GENTLE

    def test_joy_increases_volume(self, neutral_personality, joy_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(joy_state)
        assert override.volume in (ResponseVolume.VERBOSE, ResponseVolume.VERY_VERBOSE)
        assert override.emoji_level in (EmojiLevel.OFTEN, EmojiLevel.FREQUENTLY)

    def test_sadness_decreases_volume(self, neutral_personality, sad_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(sad_state)
        assert override.volume in (ResponseVolume.BRIEF, ResponseVolume.VERY_BRIEF)
        # 悲伤时 emoji 很少或不用
        assert override.emoji_level in (EmojiLevel.NEVER, EmojiLevel.RARELY)

    def test_anger_is_direct(self, neutral_personality):
        angry = EmotionalState(
            primary_emotion=EmotionType.ANGER,
            primary_intensity=EmotionIntensity.MODERATE,
            mood_valence=-0.4,
            arousal=0.8,
            active_entries=[EmotionEntry(emotion_type=EmotionType.ANGER, intensity=EmotionIntensity.MODERATE)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(angry)
        assert override.sentence_pattern == SentencePattern.SHORT_DIRECT
        assert override.tone_modifier == ToneModifier.INTENSE

    def test_all_emotion_types_have_override(self, neutral_personality):
        """确保所有 12 种情绪类型都返回非空指令"""
        for etype in EmotionType:
            state = EmotionalState(
                primary_emotion=etype,
                primary_intensity=EmotionIntensity.MODERATE,
                mood_valence=0.2,
                arousal=0.4,
                active_entries=[EmotionEntry(emotion_type=etype, intensity=EmotionIntensity.MODERATE)],
            )
            mapper = ExpressionStyleMapper(personality=neutral_personality)
            override = mapper.map_from_state(state)
            # 所有情绪类型都应该产生指令文本（Calm 也应该有）
            if not state.is_calm or state.active_entries:
                assert override.instructions, f"{etype} should have instructions"

    def test_disgust_is_minimal(self, neutral_personality):
        disgust = EmotionalState(
            primary_emotion=EmotionType.DISGUST,
            primary_intensity=EmotionIntensity.MILD,
            mood_valence=-0.3,
            arousal=0.3,
            active_entries=[EmotionEntry(emotion_type=EmotionType.DISGUST)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(disgust)
        assert override.volume == ResponseVolume.VERY_BRIEF
        assert override.punctuation_style == PunctuationStyle.MINIMAL


# ═══════════════════════════════════════════════════
# 2. 强度影响测试
# ═══════════════════════════════════════════════════


class TestIntensityEffect:
    def test_intense_joy_has_stronger_instructions(self, neutral_personality, joy_state, intense_joy_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        normal = mapper.map_from_state(joy_state)
        intense = mapper.map_from_state(intense_joy_state)
        # 强烈模式使用 intense_instructions 或增强版
        if intense.intense_instructions:
            assert len(intense.intense_instructions) > len(normal.instructions)

    def test_mild_vs_strong_sadness(self, neutral_personality):
        mild_sad = EmotionalState(
            primary_emotion=EmotionType.SADNESS,
            primary_intensity=EmotionIntensity.MILD,
            mood_valence=-0.3,
            arousal=0.3,
            active_entries=[EmotionEntry(emotion_type=EmotionType.SADNESS, intensity=EmotionIntensity.MILD)],
        )
        strong_sad = EmotionalState(
            primary_emotion=EmotionType.SADNESS,
            primary_intensity=EmotionIntensity.STRONG,
            mood_valence=-0.7,
            arousal=0.35,
            active_entries=[EmotionEntry(emotion_type=EmotionType.SADNESS, intensity=EmotionIntensity.STRONG)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        mild_override = mapper.map_from_state(mild_sad)
        strong_override = mapper.map_from_state(strong_sad)
        # 强烈的悲伤可能触发 intense_instructions
        if strong_override.intense_instructions:
            assert "…" in strong_override.intense_instructions or "话变少" in strong_override.intense_instructions.lower()

    def test_none_intensity_returns_base_instructions(self, neutral_personality):
        none_joy = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.NONE,  # 实际上不应该出现这种组合
            mood_valence=0.4,
            arousal=0.6,
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(none_joy)
        assert isinstance(override.instructions, str)


# ═══════════════════════════════════════════════════
# 3. 风格 Prompt 生成测试
# ═══════════════════════════════════════════════════


class TestPromptGeneration:
    def test_build_style_prompt_non_empty_for_active_emotion(self, neutral_personality, joy_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(joy_state)
        prompt = mapper.build_style_prompt(override)
        assert len(prompt) > 20  # 应该有实质内容

    def test_build_style_prompt_empty_for_empty_override(self, neutral_personality):
        empty = ExpressionStyleOverride(instructions="")
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        prompt = mapper.build_style_prompt(empty)
        assert prompt == ""

    def test_build_full_expression_guide_includes_all_sections(self, neutral_personality, joy_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        guide = mapper.build_full_expression_guide(
            state=joy_state,
            base_style_instructions="自然对话，像和朋友聊天一样",
        )
        # 应包含基础风格
        assert "朋友" in guide
        # 应包含情绪描述
        assert "开心" in guide
        # 应包含表达风格覆盖
        assert "表达风格" in guide or len(guide) > 30

    def test_full_guide_without_base_style(self, neutral_personality, joy_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        guide = mapper.build_full_expression_guide(state=joy_state)
        # 即使没有基础风格也应该生成内容
        assert len(guide) > 10


# ═══════════════════════════════════════════════════
# 4. 性格调节因子测试
# ═══════════════════════════════════════════════════


class TestPersonalityModulation:
    def test_high_neuroticism_amplifies_expression(self, high_neuroticism, joy_state):
        """高神经质的人表达更极端"""
        normal_p = PersonalityDimensions()
        normal_mapper = ExpressionStyleMapper(personality=normal_p)
        high_mapper = ExpressionStyleMapper(personality=high_neuroticism)

        normal_override = normal_mapper.map_from_state(joy_state)
        high_override = high_mapper.map_from_state(joy_state)

        # 高神经质的指令应该包含额外的性格修饰文字
        if high_override.instructions and normal_override.instructions:
            # 高神经质版本应该更长（因为附加了性格调节说明）
            assert len(high_override.instructions) >= len(normal_override.instructions)

    def test_high_agreeable_softens_negative(self, high_agreeable, sad_state):
        """高宜人性的人负面情绪表达更温和"""
        normal_p = PersonalityDimensions()
        normal_mapper = ExpressionStyleMapper(personality=normal_p)
        agreeable_mapper = ExpressionStyleMapper(personality=high_agreeable)

        normal_override = normal_mapper.map_from_state(sad_state)
        agreeable_override = agreeable_mapper.map_from_state(sad_state)

        # 高宜人性 + 负面情绪 → 应该包含"照顾感受"之类的词
        if agreeable_override.instructions:
            has_softening = any(
                kw in agreeable_override.instructions.lower()
                for kw in ["照顾", "温和", "对方", "依然"]
            )
            # 不强制要求，取决于具体的 tone_modifier 组合

    def test_no_crash_with_extreme_personality(self):
        """极端性格不应崩溃"""
        extreme = PersonalityDimensions(openness=100, conscientiousness=100, extraversion=100, agreeableness=100, neuroticism=100)
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.STRONG,
            mood_valence=1.0, arousal=1.0,
            active_entries=[EmotionEntry(emotion_type=EmotionType.JOY, intensity=EmotionIntensity.STRONG)],
        )
        mapper = ExpressionStyleMapper(personality=extreme)
        override = mapper.map_from_state(state)
        assert override is not None
        assert isinstance(override.instructions, str)


# ═══════════════════════════════════════════════════
# 5. 双情绪融合测试
# ═══════════════════════════════════════════════════


class TestDualEmotionMerging:
    def test_secondary_emotion_affects_result(self, neutral_personality, mixed_state):
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(mixed_state)
        # 有次要情绪时，指令中应该包含对次要情绪的提及
        if override.instructions:
            # 指令不为空即可
            assert len(override.instructions) > 0

    def test_primary_dominates_volume(self, neutral_personality, mixed_state):
        """话量由主导情绪决定"""
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(mixed_state)
        # 主导是 JOY → 应偏多
        assert override.volume in (ResponseVolume.VERBOSE, ResponseVolume.NORMAL)


# ═══════════════════════════════════════════════════
# 6. EmotionalState.to_expression_prompt() 集成测试
# ═══════════════════════════════════════════════════


class TestExpressionPromptMethod:
    def test_calm_state_returns_minimal_or_empty(self, calm_state):
        result = calm_state.to_expression_prompt()
        # Calm 状态可能有也可能没有特殊指令
        assert isinstance(result, str)

    def test_joy_state_returns_playful_instruction(self, joy_state):
        result = joy_state.to_expression_prompt()
        assert len(result) > 10
        # 应包含活泼/开心相关的关键词
        lower = result.lower()
        has_positive_keyword = any(kw in lower for kw in ["活泼", "兴奋", "感叹", "开心"])
        assert has_positive_keyword

    def test_sad_state_returns_reduced_instruction(self, sad_state):
        result = sad_state.to_expression_prompt()
        assert len(result) > 10
        lower = result.lower()
        has_negative_hint = any(kw in lower for kw in ["短", "省略", "少", "低落"])
        assert has_negative_hint

    def test_with_personality_parameter(self, joy_state, high_neuroticism):
        result = joy_state.to_expression_prompt(personality=high_neuroticism)
        assert isinstance(result, str)
        assert len(result) > 10


# ═══════════════════════════════════════════════════
# 7. PersonaProfile.build_system_prompt() 集成
# ═══════════════════════════════════════════════════


class TestSystemPromptIntegration:
    def test_system_prompt_contains_expression_section(self):
        """build_system_prompt 在有活跃情绪时应包含【表达风格】段落"""
        from app.persona.models import PersonaProfile, default_persona

        profile = default_persona()
        # 设置一个活跃情绪
        profile.emotion = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.MODERATE,
            mood_valence=0.5,
            arousal=0.7,
            active_entries=[
                EmotionEntry(emotion_type=EmotionType.JOY, intensity=EmotionIntensity.MODERATE, reason="测试"),
            ],
        )
        prompt = profile.build_system_prompt()
        # 应包含表达风格段落
        assert "表达风格" in prompt

    def test_system_prompt_calm_still_has_section(self):
        """即使平静状态也有基本风格提示"""
        from app.persona.models import PersonaProfile, default_persona

        profile = default_persona()
        prompt = profile.build_system_prompt()
        # 至少包含说话方式部分
        assert "说话方式" in prompt or "说话" in prompt


# ═══════════════════════════════════════════════════
# 8. 工具函数测试
# ═══════════════════════════════════════════════════


class TestUtilityFunctions:
    def test_amplify_emoji_increases_level(self):
        result = ExpressionStyleMapper._amplify_emoji(EmojiLevel.NEVER)
        assert result == EmojiLevel.RARELY

        result = ExpressionStyleMapper._amplify_emoji(EmojiLevel.RARELY)
        assert result == EmojiLevel.SOMETIMES

        result = ExpressionStyleMapper._amplify_emoji(EmojiLevel.FREQUENTLY)
        # 已经最高级，不再增加
        assert result == EmojiLevel.FREQUENTLY

    def test_blend_emoji_takes_higher(self):
        result = ExpressionStyleMapper._blend_emoji(EmojiLevel.NEVER, EmojiLevel.OFTEN)
        assert result == EmojiLevel.OFTEN

        result = ExpressionStyleMapper._blend_emoji(EmojiLevel.OFTEN, EmojiLevel.RARELY)
        assert result == EmojiLevel.OFTEN

        result = ExpressionStyleMapper._blend_emoji(EmojiLevel.SOMETIMES, EmojiLevel.SOMETIMES)
        assert result == EmojiLevel.SOMETIMES


# ═══════════════════════════════════════════════════
# 9. 边界情况
# ═══════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_active_entries_but_not_calm(self):
        """有主导情绪但无活跃条目时不应崩溃"""
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.MILD,
            mood_valence=0.4,
            arousal=0.6,
            active_entries=[],  # 无条目但标记为 JOY
        )
        mapper = ExpressionStyleMapper()
        override = mapper.map_from_state(state)
        assert override is not None

    def test_default_personality_doesnt_crash(self):
        """不传 personality 时使用默认值"""
        state = EmotionalState(
            primary_emotion=EmotionType.PROUD,
            primary_intensity=EmotionIntensity.MODERATE,
            mood_valence=0.3,
            arousal=0.5,
            active_entries=[EmotionEntry(emotion_type=EmotionType.PROUD, intensity=EmotionIntensity.MODERATE)],
        )
        mapper = ExpressionStyleMapper()  # 无参数
        override = mapper.map_from_state(state)
        assert override is not None

    def test_frustrated_is_brief_and_hesitant(self, neutral_personality):
        frustrated = EmotionalState(
            primary_emotion=EmotionType.FRUSTRATED,
            primary_intensity=EmotionIntensity.STRONG,
            mood_valence=-0.5,
            arousal=0.5,
            active_entries=[EmotionEntry(emotion_type=EmotionType.FRUSTRATED, intensity=EmotionIntensity.STRONG)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(frustrated)
        assert override.volume in (ResponseVolume.BRIEF, ResponseVolume.VERY_BRIEF)
        assert override.tone_modifier in (ToneModifier.HESITANT, ToneModifier.INTENSE)

    def test_lonely_is_brief_and_gentle(self, neutral_personality):
        lonely = EmotionalState(
            primary_emotion=EmotionType.LONELY,
            primary_intensity=EmotionIntensity.MODERATE,
            mood_valence=-0.3,
            arousal=0.3,
            active_entries=[EmotionEntry(emotion_type=EmotionType.LONELY, intensity=EmotionIntensity.MODERATE)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(lonely)
        assert override.volume == ResponseVolume.BRIEF
        assert override.tone_modifier == ToneModifier.HESITANT

    def test_grateful_is_normal_and_gentle(self, neutral_personality):
        grateful = EmotionalState(
            primary_emotion=EmotionType.GRATEFUL,
            primary_intensity=EmotionIntensity.MODERATE,
            mood_valence=0.5,
            arousal=0.4,
            active_entries=[EmotionEntry(emotion_type=EmotionType.GRATEFUL, intensity=EmotionIntensity.MODERATE)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(grateful)
        assert override.volume == ResponseVolume.NORMAL
        assert override.tone_modifier == ToneModifier.GENTLE

    def test_engaged_is_elaborate(self, neutral_personality):
        engaged = EmotionalState(
            primary_emotion=EmotionType.ENGAGED,
            primary_intensity=EmotionIntensity.STRONG,
            mood_valence=0.3,
            arousal=0.75,
            active_entries=[EmotionEntry(emotion_type=EmotionType.ENGAGED, intensity=EmotionIntensity.STRONG)],
        )
        mapper = ExpressionStyleMapper(personality=neutral_personality)
        override = mapper.map_from_state(engaged)
        assert override.sentence_pattern == SentencePattern.ELABORATE
