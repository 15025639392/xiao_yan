from __future__ import annotations

import re


def extract_preferences(content: str) -> list[str]:
    preferences: list[str] = []
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
            clean_match = match.strip("，。！？、")
            if clean_match:
                preferences.append(clean_match)
    return list(set(preferences))


def extract_habits(content: str) -> list[str]:
    habits: list[str] = []
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
            if clean_match:
                habits.append(clean_match)
    return list(set(habits))


def extract_important_events(content: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
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
            if len(clean_match) > 2:
                events.append(
                    {
                        "description": clean_match,
                        "emotion": detect_emotion(clean_match),
                    }
                )
    return events


def extract_facts(content: str) -> list[str]:
    facts: list[str] = []
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
            if clean_match:
                facts.append(clean_match)
    return list(set(facts))


def extract_learnings(content: str) -> list[str]:
    learnings: list[str] = []
    learning_patterns = [
        r"我学会了(.+)",
        r"我学会了用(.+)",
        r"我知道了(.+)",
        r"原来(.+)",
        r"现在理解了(.+)",
        r"原来可以(.+)",
        r"我理解了(.+)",
        r"我理解了(.+)的",
    ]
    for pattern in learning_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            clean_match = match.strip("，。！？、")
            if clean_match:
                learnings.append(clean_match)
    return list(set(learnings))


def detect_emotion(content: str) -> str:
    positive_words = ["开心", "高兴", "喜欢", "爱", "棒", "好", "成功", "满意", "精彩"]
    negative_words = ["难过", "伤心", "不喜欢", "讨厌", "坏", "失败", "担心", "生气", "失望"]

    positive_count = sum(1 for word in positive_words if word in content)
    negative_count = sum(1 for word in negative_words if word in content)

    if positive_count > negative_count:
        return "positive"
    if negative_count > positive_count:
        return "negative"
    return "neutral"
