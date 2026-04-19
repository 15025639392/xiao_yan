"""EmotionEngine — 情绪累积与衰减引擎

核心设计：
1. 情绪不是即时计算的，而是有持续性的事件驱动系统
2. 每个情绪事件有强度、来源、原因
3. 随时间（tick）自然衰减，回到基线
4. 性格维度影响情绪反应的幅度和持续时间
5. 情绪影响说话风格和回复内容

情绪流动模型：
  外部事件 → EmotionEngine.apply_event()
           → 更新 EmotionalState.active_entries
           → 重新计算 primary/secondary emotion
           → 影响 mood_valence 和 arousal

  tick()   → 衰减所有 active entries
           → 移除已完全衰减的条目
           → 自然回归 calm 基线
"""

from datetime import datetime, timezone
from logging import getLogger

from app.persona.emotion_inference import infer_chat_event, infer_focus_event
from app.persona.models import (
    EmotionEntry,
    EmotionIntensity,
    EmotionalState,
    EmotionType,
    PersonalityDimensions,
)

logger = getLogger(__name__)

# ── 情绪效价映射（正面/负面）──
_EMOTION_VALENCE: dict[EmotionType, float] = {
    EmotionType.JOY: 0.8,
    EmotionType.GRATEFUL: 0.7,
    EmotionType.PROUD: 0.6,
    EmotionType.SURPRISE: 0.2,       # 中性偏正
    EmotionType.CALM: 0.0,
    EmotionType.ENGAGED: 0.3,
    EmotionType.SADNESS: -0.6,
    EmotionType.ANGER: -0.7,
    EmotionType.FEAR: -0.5,
    EmotionType.DISGUST: -0.6,
    EmotionType.LONELY: -0.5,
    EmotionType.FRUSTRATED: -0.6,
}

# ── 情绪唤醒度映射 ──
_EMOTION_AROUSAL: dict[EmotionType, float] = {
    EmotionType.JOY: 0.75,
    EmotionType.ANGER: 0.9,
    EmotionType.FEAR: 0.85,
    EmotionType.SURPRISE: 0.9,
    EmotionType.PROUD: 0.65,
    EmotionType.FRUSTRATED: 0.7,
    EmotionType.CALM: 0.15,
    EmotionType.ENGAGED: 0.7,
    EmotionType.SADNESS: 0.35,
    EmotionType.LONELY: 0.4,
    EmotionType.DISGUST: 0.55,
    EmotionType.GRATEFUL: 0.45,
}

# ── 强度到数值的映射 ──
_INTENSITY_VALUE: dict[EmotionIntensity, float] = {
    EmotionIntensity.NONE: 0.0,
    EmotionIntensity.MILD: 0.25,
    EmotionIntensity.MODERATE: 0.5,
    EmotionIntensity.STRONG: 0.75,
    EmotionIntensity.INTENSE: 1.0,
}


class EmotionEngine:
    """情绪引擎

    负责：
    - 接收外部事件，生成情绪响应
    - 管理情绪的累积与衰减
    - 根据性格调整情绪反应幅度
    """

    # 默认衰减：每 tick 衰减 1 级（约 12 ticks = 1 小时）
    DEFAULT_DECAY_TICKS = 12

    def __init__(self, personality: PersonalityDimensions | None = None):
        self.personality = personality or PersonalityDimensions()

    def apply_event(
        self,
        current_state: EmotionalState,
        emotion_type: EmotionType,
        intensity: EmotionIntensity,
        reason: str = "",
        source: str = "system",
        decay_ticks: int | None = None,
    ) -> EmotionalState:
        """应用一个情绪事件，返回新的情绪状态

        Args:
            current_state: 当前情绪状态
            emotion_type: 触发的情绪类型
            intensity: 情绪强度
            reason: 情绪触发原因
            source: 来源类别
            decay_ticks: 自定义衰减时间（None 则用默认值）
        """
        # 根据性格调整实际强度
        adjusted_intensity = self._adjust_for_personality(emotion_type, intensity)

        entry = EmotionEntry(
            emotion_type=emotion_type,
            intensity=adjusted_intensity,
            reason=reason,
            source=source,
            decay_ticks=decay_ticks or self.DEFAULT_DECAY_TICKS,
        )

        new_entries = [*current_state.active_entries, entry]

        # 重新计算主导情绪
        return self._recalculate(current_state.model_copy(update={"active_entries": new_entries}))

    def tick(self, current_state: EmotionalState) -> EmotionalState:
        """时间推进一个 tick：衰减所有活跃情绪"""
        if not current_state.active_entries:
            return current_state

        remaining = []
        for entry in current_state.active_entries:
            decayed = self._decay_entry(entry)
            if decayed is not None:
                remaining.append(decayed)

        new_state = current_state.model_copy(
            update={
                "active_entries": remaining,
                "last_updated": datetime.now(timezone.utc),
            }
        )

        # 如果没有剩余活跃情绪，回归平静基线
        if not remaining:
            baseline_valence = self._baseline_valence()
            return new_state.model_copy(
                update={
                    "primary_emotion": EmotionType.CALM,
                    "primary_intensity": EmotionIntensity.NONE,
                    "secondary_emotion": None,
                    "secondary_intensity": EmotionIntensity.NONE,
                    "mood_valence": baseline_valence,
                    "arousal": 0.25,
                }
            )

        return self._recalculate(new_state)

    def infer_from_chat(
        self,
        current_state: EmotionalState,
        user_message: str,
        is_positive: bool | None = None,
    ) -> EmotionalState:
        """从聊天消息推断情绪变化

        这是一个轻量级启发式方法，不需要 LLM。
        后续可以升级为 LLM 驱动的精细情绪识别。

        Args:
            current_state: 当前情绪状态
            user_message: 用户发送的消息
            is_positive: 已知的情感倾向（None 时自动推断）
        """
        inferred_event = infer_chat_event(user_message, is_positive=is_positive)
        if inferred_event is None:
            return current_state
        emotion_type, intensity, reason = inferred_event

        return self.apply_event(
            current_state,
            emotion_type=emotion_type,
            intensity=intensity,
            reason=reason,
            source="chat",
        )

    def infer_from_focus_event(
        self,
        current_state: EmotionalState,
        event_type: str,  # "completed" / "abandoned" / "blocked" / "progress"
        focus_title: str,
    ) -> EmotionalState:
        """从当前牵挂事件推断情绪"""
        inferred_event = infer_focus_event(event_type, focus_title)
        if inferred_event is None:
            return current_state
        emotion_type, intensity, reason = inferred_event

        return self.apply_event(
            current_state,
            emotion_type=emotion_type,
            intensity=intensity,
            reason=reason,
            source="focus",
        )


    # ── 内部方法 ──────────────────────────────────────

    def _adjust_for_personality(
        self,
        emotion_type: EmotionType,
        intensity: EmotionIntensity,
    ) -> EmotionIntensity:
        """根据性格调整情绪强度

        - 高神经质 → 强度放大
        - 高宜人性 → 正面情绪增强
        - 高外向性 → joy/surprise 增强
        - 低神经质 → 负面情绪减弱
        """
        p = self.personality
        value = _INTENSITY_VALUE[intensity]
        adjustment = 1.0

        # 神经质：整体放大情绪波动
        if p.neuroticism >= 70:
            adjustment *= 1.3
        elif p.neuroticism <= 30:
            adjustment *= 0.8

        # 细粒度调整
        match emotion_type:
            case EmotionType.JOY | EmotionType.SURPRISE:
                if p.extraversion >= 70:
                    adjustment *= 1.2
            case EmotionType.ANGER | EmotionType.FRUSTRATED:
                if p.neuroticism <= 30:
                    adjustment *= 0.7
                if p.agreeableness >= 70:
                    adjustment *= 0.85  # 高宜人性的人愤怒表达更温和
            case EmotionType.SADNESS | EmotionType.LONELY:
                if p.extraversion <= 30:
                    adjustment *= 1.15  # 内向的人更容易感到孤独

        adjusted_value = min(value * adjustment, 1.0)

        # 映射回枚举
        if adjusted_value <= 0.0:
            return EmotionIntensity.NONE
        elif adjusted_value <= 0.25:
            return EmotionIntensity.MILD
        elif adjusted_value <= 0.5:
            return EmotionIntensity.MODERATE
        elif adjusted_value <= 0.75:
            return EmotionIntensity.STRONG
        else:
            return EmotionIntensity.INTENSE

    def _decay_entry(self, entry: EmotionEntry) -> EmotionEntry | None:
        """衰减单条情绪记录，返回 None 表示已完全消失"""
        current_level = _INTENSITY_VALUE[entry.intensity]

        if current_level <= 0:
            return None

        # 每次调用衰减 1 级
        levels = list(_INTENSITY_VALUE.values())
        levels_sorted = sorted(set(levels))

        # 找到当前级别的下一级
        next_value = 0.0
        for level in levels_sorted:
            if level < current_level:
                next_value = level
                break

        if next_value <= 0:
            return None

        # 反向映射回枚举
        new_intensity = EmotionIntensity.NONE
        for em_int, val in _INTENSITY_VALUE.items():
            if val == next_value:
                new_intensity = em_int
                break

        if new_intensity == EmotionIntensity.NONE:
            return None

        return entry.model_copy(update={"intensity": new_intensity})

    def _recalculate(self, state: EmotionalState) -> EmotionalState:
        """根据活跃条目重新计算主导情绪和综合指标"""
        if not state.active_entries:
            return state.model_copy(
                update={
                    "primary_emotion": EmotionType.CALM,
                    "primary_intensity": EmotionIntensity.NONE,
                    "mood_valence": self._baseline_valence(),
                    "arousal": 0.25,
                }
            )

        # 按强度加权投票
        emotion_scores: dict[EmotionType, float] = {}
        total_arousal = 0.0
        total_weight = 0.0

        for entry in state.active_entries:
            weight = _INTENSITY_VALUE[entry.intensity]
            emotion_scores[entry.emotion_type] = (
                emotion_scores.get(entry.emotion_type, 0.0) + weight
            )
            total_arousal += _EMOTION_AROUSAL.get(entry.emotion_type, 0.5) * weight
            total_weight += weight

        # 排序选出 primary / secondary
        sorted_emotions = sorted(
            emotion_scores.items(), key=lambda x: x[1], reverse=True
        )

        primary_type = sorted_emotions[0][0] if sorted_emotions else EmotionType.CALM
        primary_score = sorted_emotions[0][1] if sorted_emotions else 0.0
        secondary_type = sorted_emotions[1][0] if len(sorted_emotions) > 1 else None
        secondary_score = sorted_emotions[1][1] if len(sorted_emotions) > 1 else 0.0

        # 分数转强度
        def score_to_intensity(score: float) -> EmotionIntensity:
            normalized = score / max(total_weight, 0.01)
            if normalized >= 0.7:
                return EmotionIntensity.STRONG
            elif normalized >= 0.45:
                return EmotionIntensity.MODERATE
            elif normalized >= 0.2:
                return EmotionIntensity.MILD
            return EmotionIntensity.NONE

        # 计算综合情感效价
        mood_valence = 0.0
        for etype, score in emotion_scores.items():
            v = _EMOTION_VALENCE.get(etype, 0.0)
            mood_valence += v * score
        if total_weight > 0:
            mood_valence /= total_weight

        # 计算唤醒度
        arousal = total_arousal / max(total_weight, 0.01)

        return state.model_copy(
            update={
                "primary_emotion": primary_type,
                "primary_intensity": score_to_intensity(primary_score),
                "secondary_emotion": secondary_type,
                "secondary_intensity": score_to_intensity(secondary_score),
                "mood_valence": round(mood_valence, 3),
                "arousal": round(min(arousal, 1.0), 3),
                "last_updated": datetime.now(timezone.utc),
            }
        )

    def _baseline_valence(self) -> float:
        """返回性格决定的基线情感效价

        高外向+高开放 → 基线偏正向
        高神经质 → 基线略偏负向
        """
        p = self.personality
        baseline = 0.05  # 微微正向的默认值
        baseline += (p.extraversion + p.openness - 100) * 0.002
        baseline += (p.neuroticism - 50) * 0.001
        return round(max(-0.2, min(0.3, baseline)), 3)
