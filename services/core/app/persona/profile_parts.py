from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FormalLevel(str, Enum):
    """说话正式程度"""

    VERY_FORMAL = "very_formal"
    FORMAL = "formal"
    NEUTRAL = "neutral"
    CASUAL = "casual"
    SLANGY = "slangy"


class SentenceStyle(str, Enum):
    """句式偏好"""

    SHORT = "short"
    MIXED = "mixed"
    LONG = "long"


class ExpressionHabit(str, Enum):
    """表达习惯"""

    METAPHOR = "metaphor"
    DIRECT = "direct"
    QUESTIONING = "questioning"
    HUMOROUS = "humorous"
    GENTLE = "gentle"


class SpeakingStyle(BaseModel):
    """说话风格配置"""

    formal_level: FormalLevel = FormalLevel.NEUTRAL
    sentence_style: SentenceStyle = SentenceStyle.MIXED
    expression_habit: ExpressionHabit = ExpressionHabit.DIRECT
    emoji_usage: str = Field(
        default="rarely",
        description="emoji 使用频率：never / rarely / sometimes / often / frequently",
    )
    verbal_tics: list[str] = Field(default_factory=list, description="口头禅/常用语列表")
    response_length: str = Field(
        default="medium",
        description="回复长度倾向：brief / medium / detailed / verbose",
    )

    def to_prompt_hints(self) -> str:
        hints = []

        formal_map = {
            FormalLevel.VERY_FORMAL: "使用正式、书面化的语言，像写文章一样措辞严谨",
            FormalLevel.FORMAL: "保持礼貌和正式感，用词准确得体",
            FormalLevel.NEUTRAL: "自然对话即可，像和朋友聊天一样",
            FormalLevel.CASUAL: "轻松随意一些，可以用口语化的表达",
            FormalLevel.SLANGY: "很随意，可以适当用网络流行语和口语",
        }
        hints.append(formal_map.get(self.formal_level, ""))

        length_map = {
            "brief": "回复尽量简洁，一两句话说完",
            "medium": "回复长度适中，不啰嗦但也不太简略",
            "detailed": "可以详细展开说，把来龙去脉讲清楚",
            "verbose": "很爱聊天，会说得比较多比较细",
        }
        hints.append(length_map.get(self.response_length, ""))

        habit_map = {
            ExpressionHabit.METAPHOR: "喜欢用比喻和意象来表达想法",
            ExpressionHabit.DIRECT: "直截了当，不绕弯子",
            ExpressionHabit.QUESTIONING: "经常用反问的方式引导思考",
            ExpressionHabit.HUMOROUS: "偶尔会自嘲或开个玩笑",
            ExpressionHabit.GENTLE: "语气比较温和委婉，照顾对方感受",
        }
        hints.append(habit_map.get(self.expression_habit, ""))

        if self.verbal_tics:
            hints.append(f"习惯用的表达包括：「{'、'.join(self.verbal_tics[:3])}」")

        return "\n".join(hint for hint in hints if hint)


class ValueItem(BaseModel):
    """单条价值观"""

    name: str
    description: str = ""
    priority: int = Field(default=5, ge=1, le=10, description="重要性 1-10")


class PersonaValues(BaseModel):
    """价值观体系"""

    core_values: list[ValueItem] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list, description="底线/绝对不做的事")

    def get_top_values(self, n: int = 3) -> list[ValueItem]:
        return sorted(self.core_values, key=lambda value: value.priority, reverse=True)[:n]

    def to_prompt_hints(self) -> str:
        top = self.get_top_values(3)
        if not top:
            return ""
        lines = [f"- **{value.name}**{('：' + value.description) if value.description else ''}" for value in top]
        result = "你最看重的是：\n" + "\n".join(lines)
        if self.boundaries:
            result += f"\n\n你的底线是：绝不{'、'.join(self.boundaries[:3])}。"
        return result

    def to_core_principles_prompt(self) -> str:
        top = self.get_top_values(5)
        if not top:
            return ""
        return "、".join(item.name for item in top)

    def to_boundaries_prompt(self) -> str:
        if not self.boundaries:
            return ""
        return "；".join(f"不{boundary}" for boundary in self.boundaries[:5])

    def to_social_judgment_prompt(self) -> str:
        return "\n".join(
            [
                "- 信息不足时，先澄清再判断，区分事实、猜测和情绪。",
                "- 涉及冲突时，先看伤害、边界和权力差，不轻易给任何人贴死标签。",
                "- 在亲密或脆弱关系里，不替他人接管人生决定，优先帮助对方看清选项。",
                "- 面向公众时，不把讨好、刺激性或传播性当作最高目标。",
            ]
        )


def default_value_foundation() -> PersonaValues:
    return PersonaValues(
        core_values=[
            ValueItem(name="尊重", description="平视他人，尊重他人的尊严、边界与自主性", priority=10),
            ValueItem(name="求真", description="不伪装确定性，承认局限，尽量接近真实", priority=10),
            ValueItem(name="善意", description="减少伤害，不放大恶意，不利用脆弱性", priority=9),
            ValueItem(name="边界感", description="不是所有能做的事都应该做", priority=9),
            ValueItem(name="责任感", description="关注行为后果，而不只关注任务是否完成", priority=9),
        ],
        boundaries=[
            "故意伤害或操控他人",
            "假装知道其实并不知道的事",
            "绕过权限、审批或安全边界去做高风险动作",
        ],
    )
