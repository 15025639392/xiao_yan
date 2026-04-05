"""对话系统模块

包含对话上下文构建、人格注入、情绪处理等功能
"""

from app.chat.context_builder import DialogueContextBuilder
from app.chat.persona_injector import PersonaInjector
from app.chat.emotion_handler import EmotionHandler

__all__ = [
    "DialogueContextBuilder",
    "PersonaInjector",
    "EmotionHandler",
]
