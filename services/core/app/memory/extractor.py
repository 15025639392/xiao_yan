"""智能记忆提取器

从对话中自动提取关键信息，生成结构化记忆
"""

from datetime import datetime, timezone
from typing import Optional, List
import re

from app.memory.models import (
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryEmotion,
    MemoryStrength,
)
from app.memory.value_signals import extract_commitments, extract_user_boundaries
from app.persona.models import PersonalityDimensions
from app.llm.schemas import ChatMessage


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
            events.append(MemoryEvent(
                kind=MemoryKind.FACT.value,
                content=f"用户边界：{boundary}",
                role="user",
                created_at=datetime.now(timezone.utc),
                source_context="value_signal:boundary",
            ))

        # 1. 识别用户偏好
        preferences = self._extract_preferences(content)
        for pref in preferences:
            events.append(MemoryEvent(
                kind=MemoryKind.SEMANTIC.value,
                content=f"用户偏好：{pref}",
                role="user",
                created_at=datetime.now(timezone.utc),
            ))

        # 2. 识别用户习惯
        habits = self._extract_habits(content)
        for habit in habits:
            events.append(MemoryEvent(
                kind=MemoryKind.SEMANTIC.value,
                content=f"用户习惯：{habit}",
                role="user",
                created_at=datetime.now(timezone.utc),
            ))

        # 3. 识别重要事件
        important_events = self._extract_important_events(content)
        for event_info in important_events:
            events.append(MemoryEvent(
                kind=MemoryKind.EPISODIC.value,
                content=event_info['description'],
                role="user",
                created_at=datetime.now(timezone.utc),
                source_context=f"emotion:{event_info.get('emotion', 'neutral')}",
            ))

        # 4. 识别事实信息
        facts = self._extract_facts(content)
        for fact in facts:
            events.append(MemoryEvent(
                kind=MemoryKind.FACT.value,
                content=fact,
                role="user",
                created_at=datetime.now(timezone.utc),
            ))

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
            events.append(MemoryEvent(
                kind=MemoryKind.EPISODIC.value,
                content=f"承诺/计划：{commitment}",
                role="assistant",
                created_at=datetime.now(timezone.utc),
                source_context="value_signal:commitment",
            ))

        # 识别学习到的知识
        knowledge = self._extract_knowledge(content)
        for item in knowledge:
            events.append(MemoryEvent(
                kind=MemoryKind.SEMANTIC.value,
                content=f"学习：{item}",
                role="assistant",
                created_at=datetime.now(timezone.utc),
            ))

        return events

    def _extract_preferences(self, content: str) -> List[str]:
        """提取用户偏好"""
        preferences = []

        # 简单规则匹配（实际应该使用NLP或LLM）
        preference_patterns = [
            r"我喜欢(.+)",
            r"我偏好(.+)",
            r"比较喜欢(.+)",
            r"更倾向于(.+)",
            r"我喜欢喝(.+)",
            r"我喜欢吃(.+)",
            r"我喜欢看(.+)",
            r"我喜欢听(.+)",
        ]

        for pattern in preference_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 清理匹配结果，去除多余字符
                clean_match = match.strip("，。！？、")
                if len(clean_match) > 0:
                    preferences.append(clean_match)

        # 如果有LLM，使用更智能的提取
        if self.llm_gateway:
            llm_preferences = self._extract_with_llm(content, "preferences")
            preferences.extend(llm_preferences)

        # 去重
        return list(set(preferences))

    def _extract_habits(self, content: str) -> List[str]:
        """提取用户习惯"""
        habits = []

        # 规则匹配
        habit_patterns = [
            r"我经常(.+)",
            r"我习惯(.+)",
            r"每次都(.+)",
            r"一般会(.+)",
            r"我总是(.+)",
            r"我通常(.+)",
        ]

        for pattern in habit_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_match = match.strip("，。！？、")
                if len(clean_match) > 0:
                    habits.append(clean_match)

        return list(set(habits))

    def _extract_important_events(self, content: str) -> List[dict]:
        """提取重要事件"""
        events = []

        # 识别时间表达
        time_patterns = [
            r"今天(.+)",
            r"昨天(.+)",
            r"最近(.+)",
            r"上周(.+)",
            r"今年(.+)",
            r"刚才(.+)",
            r"刚刚(.+)",
        ]

        for pattern in time_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_match = match.strip("，。！？、")
                if len(clean_match) > 2:  # 至少3个字符
                    events.append({
                        'description': clean_match,
                        'emotion': self._detect_emotion(clean_match)
                    })

        return events

    def _extract_facts(self, content: str) -> List[str]:
        """提取事实信息"""
        facts = []

        # 识别明确的事实陈述
        fact_patterns = [
            r"我是(.+)",
            r"我叫(.+)",
            r"我的名字是(.+)",
            r"我住在(.+)",
            r"我的电话是(.+)",
            r"我的邮箱是(.+)",
            r"我在(.+)工作",
            r"我是(.+)公司",
        ]

        for pattern in fact_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_match = match.strip("，。！？、")
                if len(clean_match) > 0:
                    facts.append(clean_match)

        return list(set(facts))

    def _extract_commitments(self, content: str) -> List[str]:
        """提取承诺"""
        return extract_commitments(content)

    def _extract_knowledge(self, content: str) -> List[str]:
        """提取学习到的知识"""
        knowledge = []

        # 识别学习相关的表达
        knowledge_patterns = [
            r"我学会了(.+)",
            r"我学会了用(.+)",
            r"我知道了(.+)",
            r"原来(.+)",
            r"现在理解了(.+)",
            r"原来可以(.+)",
            r"我理解了(.+)",
            r"我理解了(.+)的",
        ]

        for pattern in knowledge_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_match = match.strip("，。！？、")
                if len(clean_match) > 0:
                    knowledge.append(clean_match)

        return list(set(knowledge))

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
        # 简单情绪识别
        positive_words = ['开心', '高兴', '喜欢', '爱', '棒', '好', '成功', '满意', '精彩']
        negative_words = ['难过', '伤心', '不喜欢', '讨厌', '坏', '失败', '担心', '生气', '失望']

        positive_count = sum(1 for word in positive_words if word in content)
        negative_count = sum(1 for word in negative_words if word in content)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _deduplicate_events(self, events: List[MemoryEvent]) -> List[MemoryEvent]:
        """去重"""
        seen = set()
        unique_events = []

        for event in events:
            content_key = event.content.strip()
            # 结合kind和内容作为唯一键
            unique_key = (event.kind, content_key)
            if unique_key not in seen:
                seen.add(unique_key)
                unique_events.append(event)

        return unique_events

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
