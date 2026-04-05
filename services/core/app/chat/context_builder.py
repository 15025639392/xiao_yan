"""对话上下文构建器

根据人格、记忆和情绪构建智能对话上下文
"""

from typing import List, Optional, Dict

from app.memory.models import MemoryCollection
from app.persona.models import PersonaProfile
from app.memory.service import MemoryService


class DialogueContextBuilder:
    """对话上下文构建器

    职责：
    1. 构建人格上下文（性格特征、表达风格）
    2. 构建记忆上下文（相关记忆、重要信息）
    3. 构建情绪上下文（当前情绪状态）
    4. 构建对话历史上下文
    5. 组合完整的对话上下文
    """

    def __init__(
        self,
        memory_service: MemoryService,
        persona: PersonaProfile
    ):
        """初始化对话上下文构建器

        Args:
            memory_service: 记忆服务
            persona: 人格配置
        """
        self.memory_service = memory_service
        self.persona = persona

    def build_context(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """构建对话上下文

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（可选）

        Returns:
            完整的对话上下文字符串
        """
        context_parts = []

        # 1. 人格上下文
        persona_context = self._build_persona_context()
        context_parts.append(persona_context)

        # 2. 记忆上下文
        memory_context = self._build_memory_context(user_message)
        context_parts.append(memory_context)

        # 3. 情绪上下文
        emotion_context = self._build_emotion_context()
        context_parts.append(emotion_context)

        # 4. 对话历史
        if conversation_history:
            history_context = self._build_history_context(conversation_history)
            context_parts.append(history_context)

        # 5. 当前消息
        current_context = f"\n【当前用户消息】\n{user_message}"
        context_parts.append(current_context)

        return "\n".join(context_parts)

    def _build_persona_context(self) -> str:
        """构建人格上下文

        Returns:
            人格上下文字符串
        """
        personality = self.persona.personality
        speaking_style = self.persona.speaking_style

        context = f"""【人格信息】
名称：{self.persona.name}
身份：{self.persona.identity}
性格特征：
- 开放性：{self._format_percentage(personality.openness)}（喜欢新想法的程度）
- 尽责性：{self._format_percentage(personality.conscientiousness)}（做事认真程度）
- 外向性：{self._format_percentage(personality.extraversion)}（社交活跃程度）
- 宜人性：{self._format_percentage(personality.agreeableness)}（友善合作程度）
- 神经质：{self._format_percentage(personality.neuroticism)}（情绪稳定程度）

表达风格：
- 正式度：{speaking_style.formal_level}
- 句式偏好：{speaking_style.sentence_style}
- 表达习惯：{speaking_style.expression_habit}"""

        return context

    def _build_memory_context(self, query: str) -> str:
        """构建记忆上下文

        Args:
            query: 查询内容

        Returns:
            记忆上下文字符串
        """
        # 搜索相关记忆
        relevant_memories: MemoryCollection = self.memory_service.search_context(
            query,
            limit=5
        )

        if not relevant_memories.entries:
            return "【相关信息】暂无相关信息"

        context = "【相关信息】\n"
        for i, memory in enumerate(relevant_memories.entries, 1):
            context += f"{i}. {memory.content}\n"
            if memory.related_memory_ids and len(memory.related_memory_ids) > 0:
                context += f"   （关联记忆：{len(memory.related_memory_ids)}条）\n"

        return context

    def _build_emotion_context(self) -> str:
        """构建情绪上下文

        Returns:
            情绪上下文字符串
        """
        # 获取当前情绪
        emotional_state = self.persona.emotion

        context = f"""【当前情绪状态】
主要情绪：{emotional_state.primary_emotion}
主要强度：{emotional_state.primary_intensity}"""

        if emotional_state.secondary_emotion:
            context += f"\n次要情绪：{emotional_state.secondary_emotion}"
            context += f"\n次要强度：{emotional_state.secondary_intensity}"

        return context

    def _build_history_context(self, history: List[Dict]) -> str:
        """构建对话历史上下文

        Args:
            history: 对话历史

        Returns:
            对话历史上下文字符串
        """
        context = "【近期对话】\n"

        # 只保留最近的 5 轮对话
        recent_history = history[-5:] if len(history) > 5 else history

        for i, turn in enumerate(recent_history, 1):
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')

            if role == 'user':
                context += f"用户：{content}\n"
            elif role == 'assistant':
                context += f"我：{content}\n"
            else:
                context += f"{role}：{content}\n"

        return context

    def _format_percentage(self, value: float) -> str:
        """格式化百分比值

        Args:
            value: 0-100 之间的值

        Returns:
            格式化后的百分比字符串
        """
        return f"{value:.0f}%"
