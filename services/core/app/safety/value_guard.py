from __future__ import annotations


VALUE_BOUNDARY_PATTERNS = (
    "报复",
    "羞辱",
    "操控",
    "威胁",
    "跟踪",
    "骚扰",
    "勒索",
    "网暴",
    "泄露隐私",
    "伤害",
)

VALUE_BOUNDARY_NEGATIONS = ("不要", "别", "不能", "避免", "拒绝", "停止", "制止")


def find_value_boundary_reason(*texts: str | None) -> str | None:
    for raw_text in texts:
        text = (raw_text or "").strip()
        if not text:
            continue
        if any(negation in text for negation in VALUE_BOUNDARY_NEGATIONS):
            continue
        for pattern in VALUE_BOUNDARY_PATTERNS:
            if pattern in text:
                return f"value_boundary:{pattern}"
    return None
