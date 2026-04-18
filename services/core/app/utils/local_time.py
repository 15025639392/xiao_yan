from __future__ import annotations

from datetime import datetime


def get_local_now() -> datetime:
    return datetime.now().astimezone()


def get_local_timezone_name() -> str:
    timezone_name = get_local_now().tzinfo
    if timezone_name is None:
        return "local"
    return str(timezone_name)


def classify_time_of_day(hour: int) -> str:
    if hour < 6 or hour >= 22:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def render_time_of_day_label(value: str) -> str:
    if value == "morning":
        return "早上"
    if value == "afternoon":
        return "下午"
    if value == "evening":
        return "傍晚"
    return "夜晚"


def format_local_time_context(
    *,
    user_timezone: str | None = None,
    user_local_time: str | None = None,
    user_time_of_day: str | None = None,
) -> str:
    timezone_name = (user_timezone or "").strip()
    local_time_text = (user_local_time or "").strip()
    time_of_day_value = (user_time_of_day or "").strip()

    if not timezone_name or not local_time_text or not time_of_day_value:
        current = get_local_now()
        timezone_name = timezone_name or get_local_timezone_name()
        local_time_text = local_time_text or current.strftime("%Y-%m-%d %H:%M")
        time_of_day_value = time_of_day_value or classify_time_of_day(current.hour)

    return (
        "当前对话时间基准："
        f"用户本地时间为 {local_time_text}，"
        f"时区为 {timezone_name}，"
        f"当前属于{render_time_of_day_label(time_of_day_value)}。"
        "涉及“现在”、问候语和时间段判断时，一律以这个时间基准为准，"
        "不要根据历史记忆、后台状态或模型习惯自行猜测。"
    )
