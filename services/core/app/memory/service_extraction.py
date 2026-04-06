from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from app.llm.schemas import ChatMessage
from app.memory.models import MemoryEmotion, MemoryEntry, MemoryEvent, MemoryKind, MemoryStrength

if TYPE_CHECKING:
    from app.memory.service import MemoryService

logger = getLogger(__name__)


class MemoryExtractionMixin:
    def extract_from_conversation(
        self: "MemoryService",
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
    ) -> list[MemoryEntry]:
        extracted: list[MemoryEntry] = []

        pref_patterns = [
            ("我喜欢", "用户表达了喜好", 7),
            ("我不喜欢", "用户表达了厌恶", 7),
            ("我讨厌", "用户表达了讨厌的事物", 7),
            ("我喜欢用", "用户的使用偏好", 6),
            ("习惯用", "用户的使用习惯", 6),
            ("我是", "用户的自我介绍", 8),
            ("我叫", "用户的姓名", 9),
            ("我的名字", "用户的姓名信息", 9),
            ("记得", "希望数字人记住的事", 8),
            ("别忘了", "重要提醒", 9),
            ("以后", "未来的约定或计划", 7),
            ("明天", "时间相关的约定", 6),
            ("下周", "时间相关的约定", 6),
            ("答应", "承诺事项", 9),
            ("保证", "承诺事项", 9),
            ("一定", "强调性承诺", 8),
        ]

        for pattern, description, importance in pref_patterns:
            if pattern in user_message:
                sentence = self._extract_sentence(user_message, pattern)
                entry = self._build_entry(
                    kind=MemoryKind.FACT,
                    content=sentence or f"{description}：{user_message[:60]}",
                    role="user",
                    strength=MemoryStrength.VIVID if importance >= 8 else MemoryStrength.NORMAL,
                    importance=importance,
                    emotion_tag=MemoryEmotion.POSITIVE if "喜欢" in pattern else MemoryEmotion.NEUTRAL,
                    subject="用户偏好",
                    source_context=f"用户说：{user_message[:40]}",
                )
                extracted.append(entry)
                break

        emotional_keywords = {
            "positive": ["太棒了", "太好了", "开心", "高兴", "爱", "感谢", "谢谢"],
            "negative": ["生气", "烦", "讨厌", "难过", "伤心", "失望", "无语"],
        }
        msg_lower = user_message.lower()

        for emotion, keywords in emotional_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    entry = self._build_entry(
                        kind=MemoryKind.EMOTIONAL,
                        content=f"用户在对话中表现出{emotion}情绪：「{user_message[:50]}」",
                        role="user",
                        strength=MemoryStrength.WEAK,
                        importance=4,
                        emotion_tag=MemoryEmotion(emotion) if emotion != "positive" else MemoryEmotion.POSITIVE,
                        source_context="情绪化对话",
                    )
                    extracted.append(entry)
                    break

        chat_user = self._build_entry(
            kind=MemoryKind.CHAT_RAW,
            content=user_message,
            role="user",
            strength=MemoryStrength.FAINT,
            importance=2,
        )
        extracted.append(chat_user)

        chat_asst = self._build_entry(
            kind=MemoryKind.CHAT_RAW,
            content=assistant_response,
            role="assistant",
            session_id=assistant_session_id,
            strength=MemoryStrength.FAINT,
            importance=2,
        )
        extracted.append(chat_asst)

        logger.info("Extracted %d memory entries from conversation", len(extracted))
        return extracted

    def process_dialogue(
        self: "MemoryService",
        dialogue: list[ChatMessage],
        context: dict | None = None,
    ) -> list[MemoryEvent]:
        if not self.repository:
            logger.warning("Cannot process dialogue: no repository")
            return []

        events = self.extractor.extract_from_dialogue(dialogue, context)

        for event in events:
            self.repository.save_event(event)

        if self.associator:
            self.associator.associate_events(events)

        logger.info("Processed %d memory events from dialogue", len(events))
        return events

    def extract_and_save(
        self: "MemoryService",
        message: ChatMessage,
        context: dict | None = None,
    ) -> list[MemoryEvent]:
        return self.process_dialogue([message], context)

    def _extract_sentence(self: "MemoryService", text: str, anchor: str) -> str | None:
        idx = text.find(anchor)
        if idx < 0:
            return None

        start = idx
        while start > 0 and text[start - 1] not in "。！？\n":
            start -= 1

        end = idx + len(anchor)
        while end < len(text) and text[end] not in "。！？\n":
            end += 1

        sentence = text[start:end].strip()
        return sentence if len(sentence) > 3 else None

