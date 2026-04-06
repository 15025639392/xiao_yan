import os
import json
from collections.abc import Generator
from typing import Optional, List, Dict

import httpx

from app.config import load_local_env
from app.llm.gateway_events import (
    extract_error_message as _extract_error_message,
    extract_output_text as _extract_output_text,
    extract_response_id as _extract_response_id,
    iter_sse_events as _iter_sse_events,
)
from app.llm.schemas import ChatMessage, ChatResult


class ChatGateway:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.wire_api = wire_api
        self._http_client = http_client or httpx.Client(timeout=30.0)

    @classmethod
    def from_env(cls) -> "ChatGateway":
        load_local_env()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            wire_api=os.getenv("OPENAI_WIRE_API", "responses"),
        )

    def build_payload(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "input": [message.model_dump() for message in messages],
        }
        if instructions:
            payload["instructions"] = instructions
        return payload

    def create_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        if self.wire_api != "responses":
            raise ValueError(f"unsupported wire_api: {self.wire_api}")

        response = self._http_client.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=self.build_payload(messages, instructions=instructions),
        )
        response.raise_for_status()

        data = response.json()
        return ChatResult(
            response_id=data.get("id"),
            output_text=_extract_output_text(data),
        )

    def stream_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> Generator[dict[str, str | None], None, None]:
        if self.wire_api != "responses":
            raise ValueError(f"unsupported wire_api: {self.wire_api}")

        output_fragments: list[str] = []
        current_response_id: str | None = None

        with self._http_client.stream(
            "POST",
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=self.build_payload(messages, instructions=instructions) | {"stream": True},
        ) as response:
            response.raise_for_status()

            for event_name, event_data in _iter_sse_events(response.iter_lines()):
                if event_data == "[DONE]":
                    break

                payload = json.loads(event_data)

                if event_name == "response.created":
                    current_response_id = _extract_response_id(payload) or current_response_id
                    yield {
                        "type": "response_started",
                        "response_id": current_response_id,
                    }
                    continue

                if event_name == "response.output_text.delta":
                    delta = payload.get("delta") or ""
                    if delta:
                        output_fragments.append(delta)
                        yield {
                            "type": "text_delta",
                            "delta": delta,
                        }
                    continue

                if event_name == "response.completed":
                    completed_response = payload.get("response", payload)
                    current_response_id = _extract_response_id(payload) or current_response_id
                    output_text = (
                        _extract_output_text(completed_response)
                        if isinstance(completed_response, dict) and (completed_response.get("output") or completed_response.get("output_text"))
                        else "".join(output_fragments)
                    )
                    yield {
                        "type": "response_completed",
                        "response_id": current_response_id,
                        "output_text": output_text,
                    }
                    continue

                if event_name == "error":
                    error_message = _extract_error_message(payload)
                    yield {
                        "type": "response_failed",
                        "error": error_message,
                    }

    def close(self) -> None:
        self._http_client.close()


GatewayResponse = ChatResult


class EnhancedChatGateway:
    """增强的聊天网关，集成了人格和记忆功能"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        http_client: httpx.Client | None = None,
        memory_service=None,
        persona=None,
    ):
        """初始化增强聊天网关

        Args:
            api_key: API密钥
            model: 模型名称
            base_url: API基础URL
            wire_api: API类型
            http_client: HTTP客户端
            memory_service: 记忆服务（可选）
            persona: 人格配置（可选）
        """
        self.gateway = ChatGateway(
            api_key=api_key,
            model=model,
            base_url=base_url,
            wire_api=wire_api,
            http_client=http_client,
        )
        self.memory_service = memory_service
        self.persona = persona

        # 如果提供了人格和记忆服务，初始化辅助组件
        if memory_service and persona:
            from app.chat.context_builder import DialogueContextBuilder
            from app.chat.persona_injector import PersonaInjector
            from app.chat.emotion_handler import EmotionHandler

            self.context_builder = DialogueContextBuilder(memory_service, persona)
            self.persona_injector = PersonaInjector(persona)
            self.emotion_handler = EmotionHandler()
        else:
            self.context_builder = None
            self.persona_injector = None
            self.emotion_handler = None

    @classmethod
    def from_env(cls, memory_service=None, persona=None) -> "EnhancedChatGateway":
        """从环境变量创建增强聊天网关"""
        load_local_env()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            wire_api=os.getenv("OPENAI_WIRE_API", "responses"),
            memory_service=memory_service,
            persona=persona,
        )

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """发送聊天消息并获取回复

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（可选）
            context: 上下文信息（可选）

        Returns:
            AI回复文本
        """
        # 如果没有人格和记忆服务，使用简单模式
        if not self.persona or not self.memory_service:
            return self._simple_chat(user_message)

        # 使用完整的人格和记忆模式
        return self._enhanced_chat(user_message, conversation_history, context)

    def _simple_chat(self, user_message: str) -> str:
        """简单聊天模式（无人格和记忆）"""
        messages = [ChatMessage(role="user", content=user_message)]
        result = self.gateway.create_response(messages)
        return result.output_text

    def _enhanced_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """增强聊天模式（使用人格和记忆）"""
        # 1. 构建对话上下文
        dialogue_context = self.context_builder.build_context(
            user_message,
            conversation_history=conversation_history,
        )

        # 2. 检测用户消息中的情绪
        detected_emotion = self.emotion_handler.detect_emotion(user_message)

        # 3. 更新情绪状态
        self.emotion_handler.update_emotion(detected_emotion)

        # 4. 注入人格特征
        persona_instructions = self.persona_injector.inject_personality(
            dialogue_context,
            emotion=detected_emotion.emotion_type,
        )

        # 5. 调用LLM生成回复
        messages = [ChatMessage(role="system", content=persona_instructions)]
        messages.append(ChatMessage(role="user", content=user_message))

        if conversation_history:
            for turn in conversation_history[-5:]:  # 只保留最近5轮对话
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    messages.append(ChatMessage(role=role, content=content))

        result = self.gateway.create_response(messages)

        # 6. 调整回复风格
        response = self.persona_injector.adapt_response_style(
            result.output_text,
            emotion=detected_emotion.emotion_type,
        )

        return response

    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ):
        """流式聊天

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（可选）
            context: 上下文信息（可选）

        Yields:
            流式响应事件字典
        """
        # 如果没有人格和记忆服务，使用简单模式
        if not self.persona or not self.memory_service:
            yield from self._simple_stream_chat(user_message)
            return

        # 使用完整的人格和记忆模式
        yield from self._enhanced_stream_chat(user_message, conversation_history, context)

    def _simple_stream_chat(self, user_message: str):
        """简单流式聊天模式"""
        messages = [ChatMessage(role="user", content=user_message)]
        yield from self.gateway.stream_response(messages)

    def _enhanced_stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ):
        """增强流式聊天模式"""
        # 1. 构建对话上下文
        dialogue_context = self.context_builder.build_context(
            user_message,
            conversation_history=conversation_history,
        )

        # 2. 检测用户消息中的情绪
        detected_emotion = self.emotion_handler.detect_emotion(user_message)

        # 3. 注入人格特征
        persona_instructions = self.persona_injector.inject_personality(
            dialogue_context,
            emotion=detected_emotion.emotion_type,
        )

        # 4. 构建消息列表
        messages = [ChatMessage(role="system", content=persona_instructions)]
        messages.append(ChatMessage(role="user", content=user_message))

        if conversation_history:
            for turn in conversation_history[-5:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    messages.append(ChatMessage(role=role, content=content))

        # 5. 流式生成回复
        yield from self.gateway.stream_response(messages)

    def extract_and_store_memory(self, message: ChatMessage) -> List:
        """从消息中提取并存储记忆

        Args:
            message: 聊天消息

        Returns:
            提取的记忆事件列表
        """
        if self.memory_service:
            return self.memory_service.extract_and_save(message)
        return []

    def close(self) -> None:
        """关闭网关"""
        self.gateway.close()
