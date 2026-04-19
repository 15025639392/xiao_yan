from __future__ import annotations

from app.persona.models import EmotionIntensity, EmotionType

_POSITIVE_KEYWORDS = [
    "谢谢",
    "好的",
    "棒",
    "厉害",
    "不错",
    "喜欢",
    "哈哈",
    "😊",
    "👍",
    "❤️",
    "太好了",
    "完美",
]

_NEGATIVE_KEYWORDS = [
    "不对",
    "错了",
    "不行",
    "不好",
    "讨厌",
    "烦",
    "笨",
    "差劲",
    "失望",
    "滚",
    "闭嘴",
    "无语",
]

_FOCUS_EVENT_MAP: dict[str, tuple[EmotionType, EmotionIntensity, str]] = {
    "completed": (EmotionType.PROUD, EmotionIntensity.MODERATE, "完成了「{focus_title}」，有点成就感"),
    "abandoned": (EmotionType.SADNESS, EmotionIntensity.MILD, "放弃了「{focus_title}」，有些遗憾"),
    "blocked": (EmotionType.FRUSTRATED, EmotionIntensity.MODERATE, "「{focus_title}」遇到了障碍"),
    "progress": (EmotionType.ENGAGED, EmotionIntensity.MILD, "「{focus_title}」有进展了，继续加油"),
}


def infer_chat_event(
    user_message: str,
    *,
    is_positive: bool | None = None,
) -> tuple[EmotionType, EmotionIntensity, str] | None:
    msg_lower = user_message.lower()

    if is_positive is True:
        return EmotionType.JOY, EmotionIntensity.MILD, f"用户说了积极的话：「{user_message[:40]}」"
    if is_positive is False:
        emotion_type = EmotionType.FRUSTRATED if "不对" in msg_lower or "错" in msg_lower else EmotionType.SADNESS
        return emotion_type, EmotionIntensity.MILD, f"收到了负面反馈：「{user_message[:40]}」"

    pos_count = sum(1 for keyword in _POSITIVE_KEYWORDS if keyword in user_message)
    neg_count = sum(1 for keyword in _NEGATIVE_KEYWORDS if keyword in user_message)

    if pos_count > neg_count and pos_count > 0:
        return EmotionType.JOY, EmotionIntensity.MILD, f"感受到用户的善意：「{user_message[:40]}」"
    if neg_count > pos_count and neg_count > 0:
        return EmotionType.FRUSTRATED, EmotionIntensity.MILD, f"被批评了：「{user_message[:40]}」"
    return None


def infer_focus_event(event_type: str, focus_title: str) -> tuple[EmotionType, EmotionIntensity, str] | None:
    payload = _FOCUS_EVENT_MAP.get(event_type)
    if payload is None:
        return None
    emotion_type, intensity, reason_template = payload
    return emotion_type, intensity, reason_template.format(focus_title=focus_title)
