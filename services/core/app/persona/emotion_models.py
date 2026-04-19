from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EmotionType(str, Enum):
    """基础情绪类型（基于 Ekman 六大基本情绪 + 扩展）"""

    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    CALM = "calm"
    ENGAGED = "engaged"
    PROUD = "proud"
    LONELY = "lonely"
    GRATEFUL = "grateful"
    FRUSTRATED = "frustrated"


class EmotionIntensity(str, Enum):
    """情绪强度等级"""

    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"
    INTENSE = "intense"


class EmotionEntry(BaseModel):
    """单条情绪记录"""

    emotion_type: EmotionType
    intensity: EmotionIntensity = EmotionIntensity.MILD
    reason: str = ""
    source: str = Field(default="system", description="触发来源：user/system/focus/world")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decay_ticks: int = Field(default=12, description="衰减所需 tick 数（约 1 分钟/tick）")


class EmotionalState(BaseModel):
    """当前情绪状态快照"""

    primary_emotion: EmotionType = EmotionType.CALM
    primary_intensity: EmotionIntensity = EmotionIntensity.NONE
    secondary_emotion: EmotionType | None = None
    secondary_intensity: EmotionIntensity = EmotionIntensity.NONE
    mood_valence: float = Field(default=0.0, ge=-1.0, le=1.0, description="情感效价 -1(负面) ~ 1(正面)")
    arousal: float = Field(default=0.3, ge=0.0, le=1.0, description="唤醒度 0(平静) ~ 1(激动)")
    active_entries: list[EmotionEntry] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_calm(self) -> bool:
        return (
            self.primary_intensity in {EmotionIntensity.NONE, EmotionIntensity.MILD}
            and self.mood_valence > -0.3
            and self.mood_valence < 0.3
        )

    @property
    def emotional_intensity_score(self) -> float:
        """综合情绪强度 0~1"""

        primary_map = {
            EmotionIntensity.NONE: 0.0,
            EmotionIntensity.MILD: 0.2,
            EmotionIntensity.MODERATE: 0.5,
            EmotionIntensity.STRONG: 0.75,
            EmotionIntensity.INTENSE: 1.0,
        }
        score = primary_map.get(self.primary_intensity, 0.0)
        if self.secondary_intensity != EmotionIntensity.NONE:
            score += primary_map.get(self.secondary_intensity, 0.0) * 0.4
        return min(score, 1.0)

    def to_prompt_hints(self) -> str:
        """将当前情绪转为 prompt 提示（基础版本：状态描述）"""

        if self.is_calm and not self.active_entries:
            return "你现在心情平静。"

        cn_names = {
            EmotionType.JOY: "开心/满足",
            EmotionType.SADNESS: "有些失落",
            EmotionType.ANGER: "有点烦躁",
            EmotionType.FEAR: "有些担忧",
            EmotionType.SURPRISE: "感到惊讶",
            EmotionType.DISGUST: "不太舒服",
            EmotionType.CALM: "平静",
            EmotionType.ENGAGED: "很投入",
            EmotionType.PROUD: "有点自豪",
            EmotionType.LONELY: "有点孤独",
            EmotionType.GRATEFUL: "心怀感激",
            EmotionType.FRUSTRATED: "有些挫败",
        }

        intensity_desc = {
            EmotionIntensity.MILD: "轻微地",
            EmotionIntensity.MODERATE: "比较",
            EmotionIntensity.STRONG: "非常",
            EmotionIntensity.INTENSE: "极其",
        }

        primary_name = cn_names.get(self.primary_emotion, self.primary_emotion.value)
        desc = intensity_desc.get(self.primary_intensity, "")
        parts = [f"你现在{desc}{primary_name}。" if desc else f"你现在{primary_name}。"]

        if self.secondary_emotion and self.secondary_intensity.value != "none":
            sec_name = cn_names.get(self.secondary_emotion, self.secondary_emotion.value)
            sec_desc = intensity_desc.get(self.secondary_intensity, "")
            parts.append(f"同时{sec_desc}带着{sec_name}的感觉。")

        if self.active_entries:
            latest = max(self.active_entries, key=lambda e: e.created_at)
            if latest.reason:
                parts.append(f"原因是：{latest.reason}")

        return "".join(parts)

    def to_expression_prompt(self, personality=None) -> str:
        """将当前情绪转为表达风格指令（表达风格增强版）"""

        from app.persona.expression_mapper import ExpressionStyleMapper

        mapper = ExpressionStyleMapper(personality=personality)
        override = mapper.map_from_state(self)
        return mapper.build_style_prompt(override)
