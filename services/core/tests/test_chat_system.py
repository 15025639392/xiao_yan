"""对话系统测试

测试对话上下文构建器、人格注入器和情绪处理器
"""

import pytest
from datetime import datetime, timezone

from app.chat.context_builder import DialogueContextBuilder
from app.chat.persona_injector import PersonaInjector
from app.chat.emotion_handler import EmotionHandler, Emotion

from app.memory.service import MemoryService
from app.memory.models import (
    MemoryKind,
    MemoryStrength,
    MemoryEmotion,
)
from app.memory.repository import InMemoryMemoryRepository
from app.persona.models import (
    PersonaProfile,
    PersonalityDimensions,
    SpeakingStyle,
    FormalLevel,
    SentenceStyle,
    ExpressionHabit,
    EmotionType,
    EmotionIntensity,
)


def test_context_builder_initialization():
    """测试对话上下文构建器的初始化"""
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        )
    )

    builder = DialogueContextBuilder(memory_service, persona)

    assert builder.memory_service is memory_service
    assert builder.persona is persona


def test_context_builder_build_persona_context():
    """测试构建人格上下文"""
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    persona = PersonaProfile(
        name="内向思考者",
        personality=PersonalityDimensions(
            openness=70,
            conscientiousness=80,
            extraversion=30,
            agreeableness=60,
            neuroticism=40
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        ),
        identity="我喜欢深度思考"
    )

    builder = DialogueContextBuilder(memory_service, persona)

    context = builder._build_persona_context()

    # 验证上下文包含关键信息
    assert "内向思考者" in context
    assert "开放性" in context
    assert "外向性" in context
    assert "表达风格" in context
    assert "我喜欢深度思考" in context


def test_context_builder_build_memory_context():
    """测试构建记忆上下文"""
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建一些测试记忆
    memory_service.create(
        kind=MemoryKind.FACT,
        content="用户喜欢喝茶",
        strength=MemoryStrength.VIVID,
        importance=8
    )

    memory_service.create(
        kind=MemoryKind.EPISODIC,
        content="用户昨天完成了一个项目",
        strength=MemoryStrength.NORMAL,
        importance=6
    )

    persona = PersonaProfile(
        name="测试",
        personality=PersonalityDimensions(),
        expression_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        ),
        identity="测试"
    )

    builder = DialogueContextBuilder(memory_service, persona)

    context = builder._build_memory_context("用户喜欢什么")

    # 验证上下文包含相关信息
    assert "相关信息" in context


def test_context_builder_build_full_context():
    """测试构建完整的对话上下文"""
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        expression_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        ),
        identity="测试"
    )

    builder = DialogueContextBuilder(memory_service, persona)

    user_message = "你好，我今天心情不错"
    conversation_history = [
        {"role": "user", "content": "早上好"},
        {"role": "assistant", "content": "早上好！今天有什么计划吗"}
    ]

    context = builder.build_context(user_message, conversation_history)

    # 验证上下文包含所有部分
    assert "【人格信息】" in context
    assert "【相关信息】" in context or "暂无相关信息" in context
    assert "【当前情绪状态】" in context
    assert "【近期对话】" in context
    assert "【当前用户消息】" in context
    assert "我今天心情不错" in context


def test_persona_injector_initialization():
    """测试人格注入器的初始化"""
    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        expression_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        ),
        identity="测试"
    )

    injector = PersonaInjector(persona)

    assert injector.persona is persona


def test_persona_injector_inject_personality():
    """测试注入人格特征"""
    persona = PersonaProfile(
        name="专业助手",
        personality=PersonalityDimensions(
            conscientiousness=90,
            extraversion=50
        ),
        expression_style=SpeakingStyle(
            formal_level=FormalLevel.FORMAL,
            sentence_style=SentenceStyle.LONG,
            expression_habit=ExpressionHabit.DIRECT
        ),
        identity="我是专业的数字助手"
    )

    injector = PersonaInjector(persona)

    base_prompt = "请回答用户的问题：你好"
    result = injector.inject_personality(base_prompt)

    # 验证结果包含人格信息
    assert "专业助手" in result
    assert "请回答用户的问题：你好" in result


def test_persona_injector_with_emotion():
    """测试带情绪的人格注入"""
    persona = PersonaProfile(
        name="测试",
        personality=PersonalityDimensions(),
        expression_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        ),
        identity="测试"
    )

    injector = PersonaInjector(persona)

    base_prompt = "请回答问题"
    result = injector.inject_personality(base_prompt, emotion=EmotionType.JOY)

    # 验证结果包含情绪信息
    assert "当前情绪" in result or "愉快" in result


def test_emotion_handler_initialization():
    """测试情绪处理器的初始化"""
    handler = EmotionHandler()

    assert handler.current_emotion.emotion_type == EmotionType.CALM
    assert len(handler.emotion_history) == 0


def test_emotion_handler_detect_positive():
    """测试检测正面情绪"""
    handler = EmotionHandler()

    text = "我今天太开心了，这个消息太棒了！"
    emotion = handler.detect_emotion(text)

    assert emotion.emotion_type == EmotionType.JOY
    assert emotion.intensity > 0


def test_emotion_handler_detect_negative():
    """测试检测负面情绪"""
    handler = EmotionHandler()

    text = "我很生气，这样的事情让人很失望"
    emotion = handler.detect_emotion(text)

    # 愤怒或失望都属于负面情绪
    assert emotion.emotion_type in [EmotionType.ANGER, EmotionType.SADNESS]
    assert emotion.intensity > 0


def test_emotion_handler_detect_neutral():
    """测试检测中性情绪"""
    handler = EmotionHandler()

    text = "我想了解一下这个功能的用法"
    emotion = handler.detect_emotion(text)

    assert emotion.emotion_type == EmotionType.CALM


def test_emotion_handler_update_emotion():
    """测试更新情绪"""
    handler = EmotionHandler()

    initial_emotion = handler.get_current_emotion()
    assert initial_emotion.emotion_type == EmotionType.CALM

    # 更新为正面情绪
    new_emotion = Emotion(emotion_type=EmotionType.JOY, intensity=0.8)
    handler.update_emotion(new_emotion)

    updated_emotion = handler.get_current_emotion()
    assert updated_emotion.emotion_type == EmotionType.JOY
    assert updated_emotion.intensity > 0


def test_emotion_handler_same_emotion_enhancement():
    """测试同种情绪的增强"""
    handler = EmotionHandler()

    # 先设置为正面情绪
    emotion1 = Emotion(emotion_type=EmotionType.JOY, intensity=0.5)
    handler.update_emotion(emotion1)

    # 再次设置为正面情绪
    emotion2 = Emotion(emotion_type=EmotionType.JOY, intensity=0.8)
    handler.update_emotion(emotion2)

    final_emotion = handler.get_current_emotion()
    assert final_emotion.emotion_type == EmotionType.JOY
    # 强度应该增强
    assert final_emotion.intensity >= 0.5


def test_emotion_handler_get_emotion_summary():
    """测试获取情绪摘要"""
    handler = EmotionHandler()

    # 添加一些情绪历史
    emotion1 = Emotion(emotion_type=EmotionType.JOY, intensity=0.7)
    handler.update_emotion(emotion1)

    emotion2 = Emotion(emotion_type=EmotionType.SADNESS, intensity=0.6)
    handler.update_emotion(emotion2)

    summary = handler.get_emotion_summary()

    assert "current_emotion" in summary
    assert "history_length" in summary
    assert "recent_emotions" in summary


def test_emotion_handler_reset_emotion():
    """测试重置情绪"""
    handler = EmotionHandler()

    # 设置一个情绪
    emotion = Emotion(emotion_type=EmotionType.JOY, intensity=0.8)
    handler.update_emotion(emotion)

    assert handler.get_current_emotion().emotion_type == EmotionType.JOY

    # 重置
    handler.reset_emotion()

    assert handler.get_current_emotion().emotion_type == EmotionType.CALM
    assert len(handler.emotion_history) == 0


def test_emotion_handler_should_adjust_response():
    """测试判断是否需要调整回复"""
    handler = EmotionHandler()

    # 低强度情绪不需要调整
    weak_emotion = Emotion(emotion_type=EmotionType.JOY, intensity=0.3)
    assert not handler.should_adjust_response(weak_emotion)

    # 高强度情绪需要调整
    strong_emotion = Emotion(emotion_type=EmotionType.JOY, intensity=0.8)
    assert handler.should_adjust_response(strong_emotion)


def test_emotion_handler_get_adjustment_hint():
    """测试获取情绪调整提示"""
    handler = EmotionHandler()

    # 正面情绪的调整提示
    joy_emotion = Emotion(emotion_type=EmotionType.JOY, intensity=0.8)
    hint = handler.get_emotion_adjustment_hint(joy_emotion)
    assert "感叹词" in hint or "积极" in hint

    # 负面情绪的调整提示
    sadness_emotion = Emotion(emotion_type=EmotionType.SADNESS, intensity=0.8)
    hint = handler.get_emotion_adjustment_hint(sadness_emotion)
    assert "温和" in hint or "理解" in hint or "支持" in hint

    # 愤怒情绪的调整提示
    anger_emotion = Emotion(emotion_type=EmotionType.ANGER, intensity=0.8)
    hint = handler.get_emotion_adjustment_hint(anger_emotion)
    assert "控制" in hint or "理性" in hint


def test_emotion_handler_multiple_keywords():
    """测试检测多个关键词"""
    handler = EmotionHandler()

    text = "我今天太开心了，这个消息让我很激动，感觉太棒了！"
    emotion = handler.detect_emotion(text)

    assert emotion.emotion_type == EmotionType.JOY
    # 多个关键词应该增强情绪强度
    assert emotion.intensity > 0.5
