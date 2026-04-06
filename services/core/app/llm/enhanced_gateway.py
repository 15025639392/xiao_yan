from __future__ import annotations

import os
from typing import Dict, List, Optional

import httpx

from app.config import load_local_env
from app.llm.schemas import ChatMessage


class EnhancedChatGateway:
    """增强的聊天网关，集成了人格和记忆功能。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        http_client: httpx.Client | None = None,
        memory_service=None,
        persona=None,
    ) -> None:
        from app.llm.gateway import ChatGateway

        self.gateway = ChatGateway(
            api_key=api_key,
            model=model,
            base_url=base_url,
            wire_api=wire_api,
            http_client=http_client,
        )
        self.memory_service = memory_service
        self.persona = persona

        if memory_service and persona:
            from app.chat.context_builder import DialogueContextBuilder
            from app.chat.emotion_handler import EmotionHandler
            from app.chat.persona_injector import PersonaInjector

            self.context_builder = DialogueContextBuilder(memory_service, persona)
            self.persona_injector = PersonaInjector(persona)
            self.emotion_handler = EmotionHandler()
        else:
            self.context_builder = None
            self.persona_injector = None
            self.emotion_handler = None

    @classmethod
    def from_env(cls, memory_service=None, persona=None) -> "EnhancedChatGateway":
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
        _ = context
        if not self.persona or not self.memory_service:
            return self._simple_chat(user_message)
        return self._enhanced_chat(user_message, conversation_history)

    def _simple_chat(self, user_message: str) -> str:
        messages = [ChatMessage(role="user", content=user_message)]
        result = self.gateway.create_response(messages)
        return result.output_text

    def _enhanced_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        dialogue_context = self.context_builder.build_context(
            user_message,
            conversation_history=conversation_history,
        )
        detected_emotion = self.emotion_handler.detect_emotion(user_message)
        self.emotion_handler.update_emotion(detected_emotion)

        persona_instructions = self.persona_injector.inject_personality(
            dialogue_context,
            emotion=detected_emotion.emotion_type,
        )
        messages = self._build_messages(user_message, persona_instructions, conversation_history)
        result = self.gateway.create_response(messages)

        return self.persona_injector.adapt_response_style(
            result.output_text,
            emotion=detected_emotion.emotion_type,
        )

    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ):
        _ = context
        if not self.persona or not self.memory_service:
            yield from self._simple_stream_chat(user_message)
            return
        yield from self._enhanced_stream_chat(user_message, conversation_history)

    def _simple_stream_chat(self, user_message: str):
        messages = [ChatMessage(role="user", content=user_message)]
        yield from self.gateway.stream_response(messages)

    def _enhanced_stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
    ):
        dialogue_context = self.context_builder.build_context(
            user_message,
            conversation_history=conversation_history,
        )
        detected_emotion = self.emotion_handler.detect_emotion(user_message)
        persona_instructions = self.persona_injector.inject_personality(
            dialogue_context,
            emotion=detected_emotion.emotion_type,
        )
        messages = self._build_messages(user_message, persona_instructions, conversation_history)
        yield from self.gateway.stream_response(messages)

    @staticmethod
    def _build_messages(
        user_message: str,
        persona_instructions: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=persona_instructions)]
        messages.append(ChatMessage(role="user", content=user_message))
        if conversation_history:
            for turn in conversation_history[-5:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    messages.append(ChatMessage(role=role, content=content))
        return messages

    def extract_and_store_memory(self, message: ChatMessage) -> List:
        if self.memory_service:
            return self.memory_service.extract_and_save(message)
        return []

    def close(self) -> None:
        self.gateway.close()


__all__ = [
    "EnhancedChatGateway",
]
