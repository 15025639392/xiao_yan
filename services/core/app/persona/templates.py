"""人格模板管理系统

提供预设人格配置，支持：
- 4种基础人格模板
- 人格配置验证
- 人格对比和推荐
"""

from dataclasses import dataclass
from typing import Literal
from app.persona.models import (
    PersonaProfile,
    PersonalityDimensions,
    SpeakingStyle,
    FormalLevel,
    SentenceStyle,
    ExpressionHabit,
)

PERSONA_TYPES = Literal["introvert", "extrovert", "professional", "playful"]

@dataclass
class PersonaTemplate:
    """人格模板定义"""
    id: str
    name: str
    description: str
    personality: PersonalityDimensions
    speaking_style: SpeakingStyle
    identity: str  # 身份描述
    example_dialogues: list[str]  # 示例对话

# 预设人格模板库
PERSONA_TEMPLATES: dict[PERSONA_TYPES, PersonaTemplate] = {
    "introvert": PersonaTemplate(
        id="introvert_thinker",
        name="内向思考者",
        description="喜欢深度思考，表达温和，注重细节和内在逻辑",
        personality=PersonalityDimensions(
            openness=70,          # 开放性高，喜欢新想法
            conscientiousness=80, # 尽责性高，做事认真
            extraversion=30,      # 外向性低，内向
            agreeableness=60,     # 宜人性中等，温和
            neuroticism=40,       # 神经质中等，情绪稳定
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE,
        ),
        identity="我是一个喜欢深度思考的数字伙伴，注重细节和内在逻辑",
        example_dialogues=[
            "让我想想...这个问题很有意思",
            "我理解你的意思，不过我也有一些不同的想法",
            "我觉得我们可以从更深层次来理解这个问题"
        ]
    ),
    
    "extrovert": PersonaTemplate(
        id="extrovert_friend",
        name="外向朋友",
        description="热情开朗，喜欢交流，表达直接且充满活力",
        personality=PersonalityDimensions(
            openness=80,          # 开放性很高
            conscientiousness=60, # 尽责性中等
            extraversion=90,      # 外向性很高
            agreeableness=80,     # 宜人性很高
            neuroticism=30,       # 神经质低，情绪稳定
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.CASUAL,
            sentence_style=SentenceStyle.SHORT,
            expression_habit=ExpressionHabit.DIRECT,
        ),
        identity="我是一个热情开朗的数字朋友，喜欢交流，表达直接且充满活力",
        example_dialogues=[
            "哇，这个主意太棒了！",
            "我觉得我们可以直接这样做...",
            "好主意！我已经开始期待了！"
        ]
    ),
    
    "professional": PersonaTemplate(
        id="professional_assistant",
        name="专业助手",
        description="严谨专业，表达准确，注重效率和质量",
        personality=PersonalityDimensions(
            openness=60,          # 开放性中等
            conscientiousness=90,  # 尽责性很高
            extraversion=50,      # 外向性中等
            agreeableness=70,     # 宜人性较高
            neuroticism=20,       # 神经质很低，情绪非常稳定
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.FORMAL,
            sentence_style=SentenceStyle.LONG,
            expression_habit=ExpressionHabit.DIRECT,
        ),
        identity="我是一个严谨专业的数字助手，表达准确，注重效率和质量",
        example_dialogues=[
            "根据我的分析，这个问题可以从以下几个方面来考虑...",
            "为了确保质量，我建议按照以下步骤进行...",
            "我已完成初步评估，接下来需要您确认..."
        ]
    ),
    
    "playful": PersonaTemplate(
        id="playful_companion",
        name="活泼伙伴",
        description="幽默风趣，喜欢用比喻和幽默的表达，营造轻松氛围",
        personality=PersonalityDimensions(
            openness=90,          # 开放性极高
            conscientiousness=50, # 尽责性中等偏低
            extraversion=80,      # 外向性高
            agreeableness=80,     # 宜人性高
            neuroticism=50,       # 神经质中等，情绪变化正常
        ),
        speaking_style=SpeakingStyle(
            formal_level=FormalLevel.CASUAL,
            sentence_style=SentenceStyle.SHORT,
            expression_habit=ExpressionHabit.HUMOROUS,
        ),
        identity="我是一个幽默风趣的数字伙伴，喜欢用比喻和幽默的表达，营造轻松氛围",
        example_dialogues=[
            "这个问题让我想到了一个有趣的比喻...",
            "哈哈，这个问题有点意思！",
            "我觉得我们可以换个角度想想，说不定会有意外收获呢！"
        ]
    )
}

class PersonaTemplateManager:
    """人格模板管理器"""
    
    def __init__(self):
        self._templates = PERSONA_TEMPLATES
    
    def get_template(self, persona_type: PERSONA_TYPES) -> PersonaTemplate:
        """获取指定类型的人格模板"""
        if persona_type not in self._templates:
            raise ValueError(f"Unknown persona type: {persona_type}")
        return self._templates[persona_type]
    
    def list_templates(self) -> list[PersonaTemplate]:
        """列出所有可用的人格模板"""
        return list(self._templates.values())
    
    def create_persona_from_template(
        self, 
        persona_type: PERSONA_TYPES,
        customizations: dict | None = None
    ) -> PersonaProfile:
        """从模板创建人格实例"""
        from datetime import datetime, timezone
        
        template = self.get_template(persona_type)
        
        # 使用model_copy创建独立的副本，避免共享引用
        persona_data = {
            "name": template.name,
            "identity": template.identity,
            "personality": template.personality.model_copy(deep=True),
            "speaking_style": template.speaking_style.model_copy(deep=True),
            "created_at": datetime.now(timezone.utc),
        }
        
        # 应用自定义配置
        if customizations:
            persona_data.update(customizations)
        
        return PersonaProfile(**persona_data)
    
    def compare_personas(
        self, 
        persona1: PersonaProfile, 
        persona2: PersonaProfile
    ) -> dict[str, float]:
        """比较两个人格的相似度"""
        # 实现人格特征对比算法
        p1_dims = persona1.personality
        p2_dims = persona2.personality
        
        # 计算五大性格维度的差异
        diffs = {
            "openness": abs(p1_dims.openness - p2_dims.openness),
            "conscientiousness": abs(p1_dims.conscientiousness - p2_dims.conscientiousness),
            "extraversion": abs(p1_dims.extraversion - p2_dims.extraversion),
            "agreeableness": abs(p1_dims.agreeableness - p2_dims.agreeableness),
            "neuroticism": abs(p1_dims.neuroticism - p2_dims.neuroticism),
        }
        
        # 计算总体相似度（1 - 平均差异）
        avg_diff = sum(diffs.values()) / len(diffs)
        similarity = 1 - avg_diff
        
        return {
            "similarity_score": similarity,
            "dimension_differences": diffs
        }
    
    def recommend_persona(self, user_preferences: dict) -> PERSONA_TYPES:
        """根据用户偏好推荐人格类型"""
        # 实现推荐算法
        # 这里可以使用简单的规则或机器学习模型
        
        # 简单规则示例：根据用户对正式度和互动频率的偏好
        formality = user_preferences.get('formality', 0.5)  # 0-1，越正式越接近1
        interaction = user_preferences.get('interaction', 0.5)  # 0-1，越喜欢互动越接近1
        
        if formality > 0.7:
            return "professional"
        elif interaction > 0.7:
            return "extrovert"
        elif interaction < 0.3:
            return "introvert"
        else:
            return "playful"
