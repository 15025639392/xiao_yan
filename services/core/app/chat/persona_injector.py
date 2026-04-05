"""人格注入器

将人格特征注入到对话生成过程中
"""

from typing import Optional

from app.persona.models import PersonaProfile, EmotionType


class PersonaInjector:
    """人格注入器

    职责：
    1. 注入人格特征到提示词
    2. 注入情绪影响
    3. 调整回复风格
    """

    def __init__(self, persona: PersonaProfile):
        """初始化人格注入器

        Args:
            persona: 人格配置
        """
        self.persona = persona

    def inject_personality(
        self,
        base_prompt: str,
        emotion: Optional[EmotionType] = None
    ) -> str:
        """注入人格特征

        Args:
            base_prompt: 基础提示词
            emotion: 情绪类型（可选）

        Returns:
            注入人格特征后的完整提示词
        """
        # 1. 构建人格指令
        persona_instructions = self.persona.build_system_prompt()

        # 2. 注入情绪影响
        if emotion:
            emotion_modifier = self._get_emotion_modifier(emotion)
            persona_instructions += f"\n{emotion_modifier}"

        # 3. 组合最终提示词
        full_prompt = f"{persona_instructions}\n\n{base_prompt}"

        return full_prompt

    def _get_emotion_modifier(self, emotion: EmotionType) -> str:
        """获取情绪修饰符

        Args:
            emotion: 情绪类型

        Returns:
            情绪修饰符字符串
        """
        emotion_modifiers = {
            EmotionType.JOY: "当前情绪：愉快，表达时可以适当使用感叹词，语气积极向上。",
            EmotionType.SADNESS: "当前情绪：有些低落，表达时语气温和，给予理解和支持。",
            EmotionType.ANGER: "当前情绪：有些烦躁，表达时注意控制语气，保持理性。",
            EmotionType.FEAR: "当前情绪：有些担忧，表达时给予安慰和鼓励。",
            EmotionType.SURPRISE: "当前情绪：惊讶，表达时可以表现出好奇和兴趣。",
            EmotionType.DISGUST: "当前情绪：不悦，表达时保持礼貌和克制。",
            EmotionType.CALM: "当前情绪：平和，表达时保持自然和稳定。",
        }

        return emotion_modifiers.get(emotion, "")

    def adapt_response_style(
        self,
        response: str,
        emotion: Optional[EmotionType] = None
    ) -> str:
        """根据人格和情绪调整回复风格

        Args:
            response: 原始回复
            emotion: 情绪类型（可选）

        Returns:
            调整风格后的回复
        """
        # 这里可以调用 ExpressionMapper 来调整表达风格
        # 简化版本：直接返回原始回复
        # 实际应用中，可以调用 app.persona.expression_mapper 进行更复杂的风格调整
        return response

    def build_system_prompt(self) -> str:
        """构建系统提示词

        Returns:
            系统提示词字符串
        """
        # 构建人格指令
        persona_instructions = self.persona.build_system_prompt()

        return persona_instructions
