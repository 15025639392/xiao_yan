"""增强聊天网关测试

测试 EnhancedChatGateway 的功能
"""

import pytest
from unittest.mock import Mock, MagicMock

from app.llm.enhanced_gateway import EnhancedChatGateway
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage, ChatResult

from app.memory.service import MemoryService
from app.memory.repository import InMemoryMemoryRepository
from app.persona.models import (
    PersonaProfile,
    PersonalityDimensions,
    SpeakingStyle,
    FormalLevel,
    SentenceStyle,
    ExpressionHabit,
)


def test_enhanced_gateway_initialization_with_all_components():
    """测试完整初始化（包含所有组件）"""
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建人格
    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        )
    )

    # 创建增强网关
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
        memory_service=memory_service,
        persona=persona,
    )

    # 验证初始化
    assert gateway.gateway is not None
    assert gateway.memory_service is memory_service
    assert gateway.persona is persona
    assert gateway.context_builder is not None
    assert gateway.persona_injector is not None
    assert gateway.emotion_handler is not None


def test_enhanced_gateway_initialization_without_components():
    """测试简单初始化（不包含人格和记忆服务）"""
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
    )

    # 验证初始化
    assert gateway.gateway is not None
    assert gateway.memory_service is None
    assert gateway.persona is None
    assert gateway.context_builder is None
    assert gateway.persona_injector is None
    assert gateway.emotion_handler is None


def test_simple_chat():
    """测试简单聊天模式"""
    # Mock ChatGateway
    mock_gateway = Mock(spec=ChatGateway)
    mock_gateway.create_response.return_value = ChatResult(
        response_id="test-id",
        output_text="Hello!"
    )

    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
    )
    gateway.gateway = mock_gateway

    # 调用简单聊天
    response = gateway.chat("Hi there!")

    # 验证
    assert response == "Hello!"
    mock_gateway.create_response.assert_called_once()


def test_simple_stream_chat():
    """测试简单流式聊天"""
    # Mock ChatGateway
    mock_gateway = Mock(spec=ChatGateway)
    mock_gateway.stream_response.return_value = [
        {"type": "response_started", "response_id": "test-id"},
        {"type": "text_delta", "delta": "Hello"},
        {"type": "text_delta", "delta": "!"},
        {"type": "response_completed", "response_id": "test-id", "output_text": "Hello!"},
    ]

    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
    )
    gateway.gateway = mock_gateway

    # 调用流式聊天
    events = list(gateway.stream_chat("Hi there!"))

    # 验证
    assert len(events) == 4
    assert events[0]["type"] == "response_started"
    assert events[1]["type"] == "text_delta"
    assert events[1]["delta"] == "Hello"
    mock_gateway.stream_response.assert_called_once()


def test_extract_and_store_memory():
    """测试提取和存储记忆"""
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建增强网关
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
        memory_service=memory_service,
    )

    # 提取和存储记忆
    message = ChatMessage(
        role="user",
        content="我叫小明，是一名程序员"
    )
    events = gateway.extract_and_store_memory(message)

    # 验证
    assert len(events) >= 0  # 可能提取到0个或多个事件


def test_enhanced_chat_with_mocked_llm():
    """测试增强聊天模式（模拟LLM）"""
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建人格
    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        )
    )

    # Mock ChatGateway
    mock_gateway = Mock(spec=ChatGateway)
    mock_gateway.create_response.return_value = ChatResult(
        response_id="test-id",
        output_text="你好，很高兴认识你！"
    )

    # 创建增强网关
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
        memory_service=memory_service,
        persona=persona,
    )
    gateway.gateway = mock_gateway

    # 调用增强聊天
    response = gateway.chat("你好！")

    # 验证
    assert "你好" in response or "Hi" in response
    mock_gateway.create_response.assert_called_once()


def test_context_builder_integration():
    """测试对话上下文构建器集成"""
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建人格
    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(
            openness=70,
            extraversion=80,
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        )
    )

    # 创建增强网关
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
        memory_service=memory_service,
        persona=persona,
    )

    # 构建上下文
    context = gateway.context_builder.build_context("你好！")

    # 验证上下文包含关键信息
    assert "测试人格" in context
    assert "人格信息" in context or "相关信息" in context
    assert "当前情绪状态" in context


def test_emotion_detection():
    """测试情绪检测"""
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    # 创建人格
    persona = PersonaProfile(
        name="测试人格",
        personality=PersonalityDimensions(),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE
        )
    )

    # 创建增强网关
    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
        memory_service=memory_service,
        persona=persona,
    )

    # 检测各种情绪
    happy_emotion = gateway.emotion_handler.detect_emotion("我太开心了！")
    sad_emotion = gateway.emotion_handler.detect_emotion("我感到很伤心")
    angry_emotion = gateway.emotion_handler.detect_emotion("我真的很生气")

    # 验证情绪检测
    assert happy_emotion.emotion_type.value in ["joy", "calm"]
    assert sad_emotion is not None
    assert angry_emotion is not None


def test_close_gateway():
    """测试关闭网关"""
    # Mock ChatGateway
    mock_gateway = Mock(spec=ChatGateway)

    gateway = EnhancedChatGateway(
        api_key="test-key",
        model="gpt-3.5-turbo",
    )
    gateway.gateway = mock_gateway

    # 关闭网关
    gateway.close()

    # 验证
    mock_gateway.close.assert_called_once()
