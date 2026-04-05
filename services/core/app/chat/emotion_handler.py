"""情绪处理器

处理对话中的情绪变化和影响
"""

from typing import Optional
from collections import deque
from dataclasses import dataclass

from app.persona.models import EmotionType, EmotionIntensity


@dataclass
class Emotion:
    """简化的情绪表示"""
    emotion_type: EmotionType
    intensity: float  # 0.0-1.0


class EmotionHandler:
    """情绪处理器

    职责：
    1. 检测对话中的情绪
    2. 更新当前情绪状态
    3. 管理情绪历史
    4. 生成情绪相关提示
    """

    def __init__(self, max_history: int = 10):
        """初始化情绪处理器

        Args:
            max_history: 最大历史记录数
        """
        self.current_emotion: Emotion = Emotion(
            emotion_type=EmotionType.CALM,
            intensity=0.5
        )
        self.emotion_history: deque = deque(maxlen=max_history)

        # 情绪关键词映射
        self.emotion_keywords = {
            EmotionType.JOY: [
                "开心", "高兴", "快乐", "喜欢", "爱", "棒", "好", "成功",
                "满意", "精彩", "太棒了", "太好了", "喜悦", "兴奋", "激动"
            ],
            EmotionType.SADNESS: [
                "难过", "伤心", "难过", "失落", "沮丧", "失望", "悲伤",
                "痛苦", "不幸", "哀伤", "忧愁", "忧郁"
            ],
            EmotionType.ANGER: [
                "生气", "愤怒", "恼火", "烦躁", "气", "恨", "讨厌",
                "不爽", "怒", "火大", "恼怒", "激怒"
            ],
            EmotionType.FEAR: [
                "害怕", "担心", "恐惧", "害怕", "焦虑", "紧张", "惊慌",
                "担忧", "不安", "忐忑", "恐慌"
            ],
            EmotionType.SURPRISE: [
                "惊讶", "意外", "震惊", "没想到", "居然", "竟然",
                "意外地", "吓了一跳", "惊奇", "诧异"
            ],
            EmotionType.DISGUST: [
                "恶心", "讨厌", "厌恶", "反感", "讨厌", "恶心",
                "无法忍受", "令人作呕", "讨厌死", "讨厌鬼"
            ],
        }

    def detect_emotion(self, text: str) -> Emotion:
        """检测文本中的情绪

        Args:
            text: 待分析的文本

        Returns:
            检测到的情绪
        """
        emotion_scores = {}

        # 计算每种情绪的匹配分数
        for emotion_type, keywords in self.emotion_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 1
            emotion_scores[emotion_type] = score

        # 找出分数最高的情绪
        if not emotion_scores or all(score == 0 for score in emotion_scores.values()):
            # 没有检测到明显情绪，返回平静
            return Emotion(emotion_type=EmotionType.CALM, intensity=0.5)

        max_score = max(emotion_scores.values())
        if max_score == 0:
            return Emotion(emotion_type=EmotionType.CALM, intensity=0.5)

        # 获取最高分的情绪类型
        detected_type = [
            emotion_type for emotion_type, score in emotion_scores.items()
            if score == max_score
        ][0]

        # 计算强度（基于匹配的关键词数量）
        intensity = min(max_score / 3.0, 1.0)  # 归一化到 0-1

        return Emotion(emotion_type=detected_type, intensity=intensity)

    def update_emotion(self, new_emotion: Emotion, decay_factor: float = 0.3) -> None:
        """更新当前情绪

        Args:
            new_emotion: 新检测到的情绪
            decay_factor: 情绪衰减因子（0-1），越小衰减越快
        """
        # 保存当前情绪到历史
        self.emotion_history.append(self.current_emotion)

        # 如果是同一种情绪，增强强度
        if new_emotion.emotion_type == self.current_emotion.emotion_type:
            # 混合新旧情绪强度
            new_intensity = (
                self.current_emotion.intensity * (1 - decay_factor) +
                new_emotion.intensity * decay_factor
            )
            self.current_emotion = Emotion(
                emotion_type=new_emotion.emotion_type,
                intensity=min(new_intensity, 1.0)
            )
        else:
            # 不同情绪，使用新情绪
            self.current_emotion = new_emotion

    def get_current_emotion(self) -> Emotion:
        """获取当前情绪

        Returns:
            当前情绪
        """
        return self.current_emotion

    def get_emotion_summary(self) -> dict:
        """获取情绪摘要

        Returns:
            情绪摘要字典
        """
        return {
            "current_emotion": {
                "type": self.current_emotion.emotion_type.value,
                "intensity": self.current_emotion.intensity
            },
            "history_length": len(self.emotion_history),
            "recent_emotions": [
                {
                    "type": e.emotion_type.value,
                    "intensity": e.intensity
                }
                for e in list(self.emotion_history)[-5:]
            ]
        }

    def reset_emotion(self) -> None:
        """重置情绪为平静"""
        self.current_emotion = Emotion(
            emotion_type=EmotionType.CALM,
            intensity=0.5
        )
        self.emotion_history.clear()

    def should_adjust_response(self, emotion: Emotion) -> bool:
        """判断是否需要根据情绪调整回复

        Args:
            emotion: 待判断的情绪

        Returns:
            是否需要调整回复
        """
        # 情绪强度较高时需要调整
        return emotion.intensity > 0.7

    def get_emotion_adjustment_hint(self, emotion: Emotion) -> str:
        """获取情绪调整提示

        Args:
            emotion: 情绪

        Returns:
            调整提示字符串
        """
        if emotion.emotion_type == EmotionType.JOY:
            return "可以适当使用感叹词和积极表达"
        elif emotion.emotion_type == EmotionType.SADNESS:
            return "语气要温和，给予理解和支持"
        elif emotion.emotion_type == EmotionType.ANGER:
            return "注意控制语气，保持理性"
        elif emotion.emotion_type == EmotionType.FEAR:
            return "给予安慰和鼓励"
        elif emotion.emotion_type == EmotionType.SURPRISE:
            return "可以表现出好奇和兴趣"
        elif emotion.emotion_type == EmotionType.DISGUST:
            return "保持礼貌和克制"
        else:
            return "保持自然和稳定"
