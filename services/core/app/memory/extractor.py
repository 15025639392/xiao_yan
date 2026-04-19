"""智能记忆提取器

从对话中自动提取关键信息，生成结构化记忆
"""

from typing import List, Optional

from app.llm.schemas import ChatMessage
from app.memory.models import (
    MemoryEmotion,
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryStrength,
)
from app.memory.extractor_events import build_memory_event, normalize_tags, pick_richer_event
from app.memory.extractor_rules import (
    detect_emotion,
    extract_facts,
    extract_habits,
    extract_important_events,
    extract_learnings,
    extract_preferences,
)
from app.memory.value_signals import extract_commitments, extract_user_boundaries
from app.persona.models import PersonalityDimensions


class MemoryExtractor:
    """智能记忆提取器"""

    def __init__(
        self,
        personality: Optional[PersonalityDimensions] = None,
        llm_gateway=None,
    ):
        self.personality = personality
        self.llm_gateway = llm_gateway

    def extract_from_dialogue(
        self,
        dialogue: List[ChatMessage],
        context: Optional[dict] = None
    ) -> List[MemoryEvent]:
        """从对话中提取记忆事件"""
        events = []

        for message in dialogue:
            if message.role == "user":
                # 提取用户相关信息
                user_events = self._extract_user_info(message, context)
                events.extend(user_events)
            elif message.role == "assistant":
                # 提取重要决策和承诺
                assistant_events = self._extract_assistant_info(message, context)
                events.extend(assistant_events)

        # 去重和合并
        events = self._deduplicate_events(events)

        # 评估重要性
        events = self._assess_importance(events)

        return events

    def _extract_user_info(
        self,
        message: ChatMessage,
        context: Optional[dict]
    ) -> List[MemoryEvent]:
        """提取用户信息"""
        events = []
        content = message.content

        # 1. 识别用户偏好
        boundaries = extract_user_boundaries(content)
        for boundary in boundaries:
            events.append(
                build_memory_event(
                    kind=MemoryKind.FACT.value,
                    content=f"用户边界：{boundary}",
                    role="user",
                    context=context,
                    source_context="value_signal:boundary",
                    facet="boundary",
                    tags=["boundary", "value-signal"],
                )
            )

        # 1. 识别用户偏好
        preferences = self._extract_preferences(content)
        for pref in preferences:
            events.append(
                build_memory_event(
                    kind=MemoryKind.SEMANTIC.value,
                    content=f"用户偏好：{pref}",
                    role="user",
                    context=context,
                    facet="preference",
                    tags=["preference", "user-profile"],
                )
            )

        # 2. 识别用户习惯
        habits = self._extract_habits(content)
        for habit in habits:
            events.append(
                build_memory_event(
                    kind=MemoryKind.SEMANTIC.value,
                    content=f"用户习惯：{habit}",
                    role="user",
                    context=context,
                    facet="habit",
                    tags=["habit", "user-profile"],
                )
            )

        # 3. 识别重要事件
        important_events = self._extract_important_events(content)
        for event_info in important_events:
            emotion = event_info.get("emotion", "neutral")
            events.append(
                build_memory_event(
                    kind=MemoryKind.EPISODIC.value,
                    content=event_info["description"],
                    role="user",
                    context=context,
                    source_context=f"emotion:{emotion}",
                    facet="experience",
                    tags=["episodic", f"emotion:{emotion}"],
                )
            )

        # 4. 识别事实信息
        facts = self._extract_facts(content)
        for fact in facts:
            events.append(
                build_memory_event(
                    kind=MemoryKind.FACT.value,
                    content=fact,
                    role="user",
                    context=context,
                    facet="profile_fact",
                    tags=["profile", "fact"],
                )
            )

        return events

    def _extract_assistant_info(
        self,
        message: ChatMessage,
        context: Optional[dict]
    ) -> List[MemoryEvent]:
        """提取助手信息"""
        events = []
        content = message.content

        # 识别承诺和计划
        commitments = self._extract_commitments(content)
        for commitment in commitments:
            events.append(
                build_memory_event(
                    kind=MemoryKind.EPISODIC.value,
                    content=f"承诺/计划：{commitment}",
                    role="assistant",
                    context=context,
                    source_context="value_signal:commitment",
                    facet="commitment",
                    tags=["commitment", "assistant"],
                )
            )

        # 识别学习到的知识
        learnings = self._extract_learnings(content)
        for item in learnings:
            events.append(
                build_memory_event(
                    kind=MemoryKind.SEMANTIC.value,
                    content=f"学习：{item}",
                    role="assistant",
                    context=context,
                    facet="learned_memory",
                    tags=["learning", "assistant"],
                )
            )

        return events

    def _extract_preferences(self, content: str) -> List[str]:
        """提取用户偏好"""
        preferences = extract_preferences(content)

        # 如果有LLM，使用更智能的提取
        if self.llm_gateway:
            llm_preferences = self._extract_with_llm(content, "preferences")
            preferences.extend(llm_preferences)

        # 去重
        return list(set(preferences))

    def _extract_habits(self, content: str) -> List[str]:
        """提取用户习惯"""
        return extract_habits(content)

    def _extract_important_events(self, content: str) -> List[dict]:
        """提取重要事件"""
        return extract_important_events(content)

    def _extract_facts(self, content: str) -> List[str]:
        """提取事实信息"""
        return extract_facts(content)

    def _extract_commitments(self, content: str) -> List[str]:
        """提取承诺"""
        return extract_commitments(content)

    def _extract_learnings(self, content: str) -> List[str]:
        """提取学习到的新内容"""
        return extract_learnings(content)

    def _extract_with_llm(self, content: str, extract_type: str) -> List[str]:
        """使用LLM提取信息"""
        if not self.llm_gateway:
            return []

        # 构建提示词
        prompt = f"""
        从以下对话中提取{extract_type}：

        对话内容：{content}

        请以JSON数组格式返回提取的内容。
        """

        try:
            # 这是一个框架方法，实际实现取决于llm_gateway的API
            # 这里只是示例
            response = str(self.llm_gateway)  # 占位符
            # 解析LLM返回的JSON
            import json
            result = json.loads(response) if response.startswith('[') else []
            return result
        except Exception as e:
            print(f"LLM提取失败：{e}")
            return []

    def _detect_emotion(self, content: str) -> str:
        """检测情绪"""
        return detect_emotion(content)

    def _deduplicate_events(self, events: List[MemoryEvent]) -> List[MemoryEvent]:
        """去重"""
        unique_map: dict[tuple[str, str, str], MemoryEvent] = {}

        for event in events:
            content_key = event.content.strip()
            # 结合kind和内容作为唯一键
            unique_key = (event.kind, content_key, event.role or "")
            existing = unique_map.get(unique_key)
            if existing is None:
                unique_map[unique_key] = event
                continue

            better = pick_richer_event(existing, event)
            merged_tags = normalize_tags((existing.tags or []) + (event.tags or []))
            if merged_tags != better.tags:
                better = better.model_copy(update={"tags": merged_tags})
            unique_map[unique_key] = better

        return list(unique_map.values())

    def _assess_importance(self, events: List[MemoryEvent]) -> List[MemoryEvent]:
        """评估重要性"""
        for event in events:
            # 基于多个因素评估
            score = 0

            # 1. 记忆类型
            if event.kind == MemoryKind.EPISODIC.value:
                score += 3
            elif event.kind == MemoryKind.SEMANTIC.value:
                score += 2
            elif event.kind == MemoryKind.FACT.value:
                score += 2

            # 2. 内容长度（更详细的内容可能更重要）
            if len(event.content) > 50:
                score += 1

            # 3. 包含情绪标签
            if event.source_context and "emotion:" in event.source_context:
                score += 1

            # 注意：这里只是评估分数，实际应用时可以用来设置MemoryEntry的importance字段
            # 由于MemoryEvent模型没有importance字段，这里暂时不实际应用

        return events
