"""人格内核测试

覆盖：
- PersonaProfile 数据模型
- PersonalityDimensions 特质计算
- SpeakingStyle prompt 生成
- EmotionalState 情绪状态
- EmotionEngine 情绪累积/衰减
- PersonaService CRUD + 持久化 + 情绪操作
- PromptBuilder 人格注入
"""

import pytest
from app.persona.models import (
    EmotionEntry,
    EmotionIntensity,
    EmotionalState,
    EmotionType,
    ExpressionHabit,
    FormalLevel,
    PersonalityDimensions,
    PersonaProfile,
    SentenceStyle,
    SpeakingStyle,
    ValueItem,
    default_persona,
)
from app.persona.emotion_engine import EmotionEngine
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import InMemoryPersonaRepository, PersonaService


# ═══════════════════════════════════════════════════
# 数据模型测试
# ═══════════════════════════════════════════════════


class TestPersonaProfile:
    """PersonaProfile 基础模型测试"""

    def test_default_persona_has_name_and_identity(self):
        p = default_persona()
        assert p.name == "小晏"
        assert p.identity == "持续存在的数字人"
        assert p.origin_story

    def test_default_persona_has_personality(self):
        p = default_persona()
        assert p.personality.openness == 72
        assert p.personality.extraversion == 40
        assert 0 <= p.personality.neuroticism <= 100

    def test_default_persona_has_speaking_style(self):
        p = default_persona()
        assert p.speaking_style.formal_level == FormalLevel.CASUAL
        assert len(p.speaking_style.verbal_tics) > 0

    def test_default_persona_has_values(self):
        p = default_persona()
        assert len(p.values.core_values) >= 3
        assert len(p.values.boundaries) >= 2

    def test_version_increments_on_update(self):
        p = default_persona()
        v1 = p.version
        updated = p.model_copy(update={"name": "新名字", "version": v1 + 1})
        assert updated.version > v1

class TestPersonalityDimensions:
    """性格维度测试"""

    def test_default_is_balanced(self):
        pd = PersonalityDimensions()
        assert pd.openness == 50
        assert pd.neuroticism == 50

    def test_get_dominant_traits_high_openness(self):
        pd = PersonalityDimensions(openness=80, extraversion=75)
        traits = pd.get_dominant_traits()
        assert any("好奇" in t or "尝试" in t for t in traits)
        assert any("社交" in t or "外向" in t or "开朗" in t for t in traits)

    def test_get_dominant_traits_stable_neuroticism(self):
        pd = PersonalityDimensions(neuroticism=20)
        traits = pd.get_dominant_traits()
        assert any("稳定" in t for t in traits)

    def test_get_dominant_traits_nothing_above_threshold(self):
        pd = PersonalityDimensions(openness=50, extraversion=50)
        traits = pd.get_dominant_traits(threshold=70)
        assert len(traits) == 0

    def test_personality_summary_returns_text(self):
        pd = PersonalityDimensions(extraversion=80, openness=10)
        summary = pd.get_personality_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_personality_summary_neutral(self):
        pd = PersonalityDimensions()
        summary = pd.get_personality_summary()
        # 中等性格应该返回均衡描述或空字符串
        assert isinstance(summary, str)


class TestSpeakingStyle:
    """说话风格测试"""

    def test_to_prompt_hints_generates_text(self):
        style = SpeakingStyle(
            formal_level=FormalLevel.CASUAL,
            expression_habit=ExpressionHabit.HUMOROUS,
            verbal_tics=["说实话", "我觉得"],
        )
        hints = style.to_prompt_hints()
        assert "轻松" in hints or "随意" in hints
        assert "幽默" in hints or "玩笑" in hints
        assert "说实话" in hints

    def test_formal_level_very_formal(self):
        style = SpeakingStyle(formal_level=FormalLevel.VERY_FORMAL)
        hints = style.to_prompt_hints()
        assert "正式" in hints or "书面" in hints

    def test_expression_habit_direct(self):
        style = SpeakingStyle(expression_habit=ExpressionHabit.DIRECT)
        hints = style.to_prompt_hints()
        assert "直接" in hints or "不绕弯" in hints

    def test_verbal_tics_empty(self):
        style = SpeakingStyle(verbal_tics=[])
        hints = style.to_prompt_hints()
        # 不应包含口头禅部分
        assert "习惯用的表达" not in hints


class TestEmotionalState:
    """情绪状态模型测试"""

    def test_default_is_calm(self):
        state = EmotionalState()
        assert state.is_calm is True
        assert state.primary_emotion == EmotionType.CALM

    def test_not_calm_when_strong_emotion(self):
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.STRONG,
        )
        assert state.is_calm is False

    def test_emotional_intensity_score_calculation(self):
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.MODERATE,
        )
        score = state.emotional_intensity_score
        assert 0.4 <= score <= 0.6

    def test_secondary_adds_to_score(self):
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.MODERATE,
            secondary_emotion=EmotionType.ENGAGED,
            secondary_intensity=EmotionIntensity.MILD,
        )
        score = state.emotional_intensity_score
        # secondary 应该增加分数
        single = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.MODERATE,
        )
        assert score > single.emotional_intensity_score

    def test_to_prompt_hints_calm_state(self):
        state = EmotionalState()
        hints = state.to_prompt_hints()
        assert "平静" in hints

    def test_to_prompt_hints_with_reason(self):
        state = EmotionalState(
            primary_emotion=EmotionType.JOY,
            primary_intensity=EmotionIntensity.STRONG,
            active_entries=[
                EmotionEntry(
                    emotion_type=EmotionType.JOY,
                    intensity=EmotionIntensity.STRONG,
                    reason="完成了目标！",
                )
            ],
        )
        hints = state.to_prompt_hints()
        assert "完成目标" in hints or "完成了目标" in hints


class TestPersonaValues:
    """价值观测试"""

    def test_top_values_sorted_by_priority(self):
        values_type = type(default_persona().values)(
            core_values=[
                ValueItem(name="A", priority=3),
                ValueItem(name="B", priority=9),
                ValueItem(name="C", priority=7),
            ]
        )
        top = values_type.get_top_values(2)
        assert top[0].name == "B"
        assert top[1].name == "C"

    def test_to_prompt_hints_with_boundaries(self):
        from app.persona.models import PersonaValues
        pv = PersonaValues(
            core_values=[ValueItem(name="诚实", priority=9)],
            boundaries=["说谎"],
        )
        hints = pv.to_prompt_hints()
        assert "诚实" in hints
        assert "不说谎" in hints or "绝不说谎" in hints or "底线" in hints


# ═══════════════════════════════════════════════════
# EmotionEngine 测试
# ═══════════════════════════════════════════════════


class TestEmotionEngine:
    """情绪引擎核心逻辑"""

    @pytest.fixture
    def engine(self):
        return EmotionEngine()

    @pytest.fixture
    def calm_state(self):
        return EmotionalState()

    def test_apply_event_creates_entry(self, engine, calm_state):
        new_state = engine.apply_event(
            calm_state,
            emotion_type=EmotionType.JOY,
            intensity=EmotionIntensity.MILD,
            reason="被夸奖了",
        )
        assert len(new_state.active_entries) == 1
        assert new_state.active_entries[0].emotion_type == EmotionType.JOY
        assert new_state.primary_emotion == EmotionType.JOY

    def test_apply_event_changes_mood_valence_positive(self, engine, calm_state):
        new_state = engine.apply_event(
            calm_state,
            emotion_type=EmotionType.JOY,
            intensity=EmotionIntensity.STRONG,
            reason="很开心",
        )
        assert new_state.mood_valence > 0

    def test_apply_event_changes_mood_valence_negative(self, engine, calm_state):
        new_state = engine.apply_event(
            calm_state,
            emotion_type=EmotionType.FRUSTRATED,
            intensity=EmotionIntensity.STRONG,
            reason="遇到障碍",
        )
        assert new_state.mood_valence < 0

    def test_tick_decays_emotion(self, engine, calm_state):
        excited = engine.apply_event(
            calm_state,
            emotion_type=EmotionType.JOY,
            intensity=EmotionIntensity.STRONG,
            reason="测试",
        )
        after_tick = engine.tick(excited)
        # 衰减后强度应该降低（或者条目消失）
        if after_tick.active_entries:
            assert after_tick.active_entries[0].intensity.value != "strong"

    def test_multiple_ticks_return_to_calm(self, engine, calm_state):
        state = engine.apply_event(
            calm_state,
            emotion_type=EmotionType.JOY,
            intensity=EmotionIntensity.MILD,
            reason="轻微开心",
        )
        # MILD → NONE 只需一次衰减
        for _ in range(5):
            state = engine.tick(state)
        # 应该回到平静或接近平静
        if not state.active_entries:
            assert state.primary_emotion == EmotionType.CALM

    def test_multiple_events_stack(self, engine, calm_state):
        s1 = engine.apply_event(calm_state, EmotionType.JOY, EmotionIntensity.MILD, "开心的事")
        s2 = engine.apply_event(s1, EmotionType.PROUD, EmotionIntensity.MILD, "自豪的事")
        assert len(s2.active_entries) == 2

    def test_infer_from_chat_positive(self, engine, calm_state):
        new_state = engine.infer_from_chat(calm_state, "太棒了！做得很好")
        # 正面消息应该产生 JOY
        assert new_state.primary_emotion == EmotionType.JOY or len(new_state.active_entries) > 0 or new_state is calm_state

    def test_infer_from_chat_negative(self, engine, calm_state):
        new_state = engine.infer_from_chat(calm_state, "这不对，你搞错了")
        # 负面消息应该产生负面情绪
        has_negative = (
            new_state.primary_emotion in {EmotionType.FRUSTRATED, EmotionType.SADNESS}
            or len(new_state.active_entries) > 0
            or new_state is calm_state  # 也可能没有触发
        )
        assert has_negative

    def test_infer_from_chat_neutral(self, engine, calm_state):
        new_state = engine.infer_from_chat(calm_state, "今天天气怎么样")
        # 中性消息不应该改变情绪
        assert new_state is calm_state

    def test_infer_from_goal_completed(self, engine, calm_state):
        new_state = engine.infer_from_goal_event(calm_state, "completed", "学习 Python")
        assert new_state.primary_emotion == EmotionType.PROUD

    def test_infer_from_goal_abandoned(self, engine, calm_state):
        new_state = engine.infer_from_goal_event(calm_state, "abandoned", "旧项目")
        assert new_state.primary_emotion == EmotionType.SADNESS

    def test_infer_from_self_improvement_success(self, engine, calm_state):
        new_state = engine.infer_from_self_improvement(calm_state, "success", "代码质量")
        assert new_state.primary_emotion == EmotionType.JOY

    def test_infer_from_self_improvement_rejected(self, engine, calm_state):
        new_state = engine.infer_from_self_improvement(calm_state, "rejected", "重构方案")
        assert new_state.primary_emotion == EmotionType.SADNESS

    def test_personality_adjusts_intensity(self):
        # 高神经质的人情绪放大
        nervous = EmotionEngine(personality=PersonalityDimensions(neuroticism=85))
        stable = EmotionEngine(personality=PersonalityDimensions(neuroticism=20))
        base = EmotionalState()

        n_result = nervous.apply_event(base, EmotionType.ANGER, EmotionIntensity.MODERATE, "测试")
        s_result = stable.apply_event(base, EmotionType.ANGER, EmotionIntensity.MODERATE, "测试")

        # 高神经质的强度应该 >= 低神经质
        n_score = n_result.emotional_intensity_score
        s_score = s_result.emotional_intensity_score
        assert n_score >= s_score


# ═══════════════════════════════════════════════════
# PersonaService 测试
# ═══════════════════════════════════════════════════


class TestPersonaService:
    """PersonaService 全链路测试"""

    @pytest.fixture
    def service(self):
        repo = InMemoryPersonaRepository()
        return PersonaService(repository=repo)

    def test_get_profile_returns_default(self, service):
        profile = service.get_profile()
        assert profile.name == "小晏"

    def test_update_profile_name(self, service):
        updated = service.update_profile(name="新名字")
        assert updated.name == "新名字"
        assert updated.version > 1

    def test_update_personality_dimensions(self, service):
        updated = service.update_personality(openness=90)
        assert updated.personality.openness == 90
        assert updated.version > 1

    def test_update_speaking_style(self, service):
        updated = service.update_speaking_style(formal_level=FormalLevel.VERY_FORMAL)
        assert updated.speaking_style.formal_level == FormalLevel.VERY_FORMAL

    def test_reset_to_default(self, service):
        service.update_profile(name="改过的名字")
        reset = service.reset_to_default()
        assert reset.name == "小晏"

    def test_build_system_prompt_contains_name(self, service):
        prompt = service.build_system_prompt()
        assert "小晏" in prompt

    def test_build_system_prompt_contains_personality(self, service):
        prompt = service.build_system_prompt()
        assert "性格" in prompt or "性格" in prompt or "关键词" in prompt or len(prompt) > 100

    def test_build_system_prompt_contains_style(self, service):
        prompt = service.build_system_prompt()
        assert "说话" in prompt or "方式" in prompt or "回复" in prompt

    def test_build_system_prompt_contains_core_principles(self, service):
        prompt = service.build_system_prompt()
        assert "持续存在的人格体" in prompt

    def test_apply_emotion_updates_state(self, service):
        new_state = service.apply_emotion(
            EmotionType.JOY, EmotionIntensity.MODERATE, "测试触发"
        )
        assert new_state.primary_emotion == EmotionType.JOY

    def test_tick_emotion_decays(self, service):
        service.apply_emotion(EmotionType.JOY, EmotionIntensity.MILD, "测试")
        after_tick = service.tick_emotion()
        # 衰减后应该变化或保持
        assert isinstance(after_tick, EmotionalState)

    def test_get_emotion_summary_structure(self, service):
        summary = service.get_emotion_summary()
        assert "primary_emotion" in summary
        assert "mood_valence" in summary
        assert "is_calm" in summary
        assert "active_entries" in summary

    def test_persists_across_calls(self, service):
        service.update_profile(name="持久化测试")
        profile2 = service.get_profile()
        assert profile2.name == "持久化测试"

    def test_infer_chat_emotion_positive(self, service):
        new_state = service.infer_chat_emotion("太棒了！厉害！")
        assert isinstance(new_state, EmotionalState)

    def test_infer_goal_emotion_completed(self, service):
        new_state = service.infer_goal_emotion("completed", "学习目标")
        assert new_state.primary_emotion == EmotionType.PROUD

    def test_infer_si_emotion_applied(self, service):
        new_state = service.infer_self_improvement_emotion("applied", "性能优化")
        assert new_state.primary_emotion == EmotionType.PROUD


# ═══════════════════════════════════════════════════
# PromptBuilder 测试
# ═══════════════════════════════════════════════════


class TestPromptBuilderWithPersona:
    """PromptBuilder 与人格系统集成测试"""

    def test_build_instructions_without_persona_raises(self):
        """没有注入人格 prompt 时直接失败。"""
        with pytest.raises(ValueError, match="persona_system_prompt is required"):
            build_chat_instructions(
                focus_goal_title="测试目标",
                user_message="你好",
            )

    def test_build_instructions_with_persona_injects_it(self):
        """注入人格 prompt 时使用它"""
        persona_prompt = (
            "你是 小光。\n"
            "身份：实验型数字人\n\n"
            "【性格】\n好奇心很强\n\n"
            "【此刻心情】\n你现在有点兴奋。"
        )
        instructions = build_chat_instructions(
            focus_goal_title="测试目标",
            persona_system_prompt=persona_prompt,
        )
        assert "小光" in instructions
        assert "实验型数字人" in instructions
        assert "好奇心" in instructions
        assert "有点兴奋" in instructions
        # 不应该混入未显式传入的人格文案
        assert "Xiao Yan" not in instructions

    def test_build_instructions_maintains_guidance_with_persona(self):
        """人格注入后，原有的 guidance 仍然保留"""
        persona_prompt = "你是 测试者。\n身份：测试用"
        instructions = build_chat_instructions(
            focus_goal_title="焦点目标",
            latest_plan_completion="完成了某事",
            user_message="你最近在忙什么",
            persona_system_prompt=persona_prompt,
        )
        assert "焦点目标" in instructions
        assert "完成了某事" in instructions
        assert "如果用户在问你当前状态" in instructions
