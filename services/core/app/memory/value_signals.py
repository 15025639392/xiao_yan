from __future__ import annotations

import re


def extract_user_boundaries(text: str) -> list[str]:
    boundary_markers = (
        "别催", "不要催", "别替我", "不要替我", "不想被", "希望先", "先自己",
        "自己想", "自己判断", "给我一点空间", "边界",
    )
    strong_keywords = ("催", "决定", "空间", "边界", "自己", "替我")

    results: list[str] = []
    for sentence in _split_sentences(text):
        if not sentence:
            continue
        if not any(marker in sentence for marker in boundary_markers):
            continue
        if not any(keyword in sentence for keyword in strong_keywords):
            continue
        results.append(sentence)

    return _deduplicate(results)


def extract_commitments(text: str) -> list[str]:
    commitment_patterns = [
        r"我答应(.+)",
        r"我承诺(.+)",
        r"我会(.+)",
        r"我一定会(.+)",
        r"我决定(.+)",
        r"计划(.+)",
        r"下次(.+)",
    ]

    results: list[str] = []
    for pattern in commitment_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            cleaned = match.strip("，。！？、 ")
            if cleaned:
                results.append(cleaned)

    return _deduplicate(results)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？\n]", text)
    return [part.strip(" ，,；;") for part in parts if part.strip(" ，,；;")]


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduplicated: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduplicated.append(item)
    return deduplicated
