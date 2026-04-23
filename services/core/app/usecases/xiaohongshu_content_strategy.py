from __future__ import annotations

import re


_MAX_TITLE_LENGTH = 20


def normalize_xiaohongshu_title(title: str, *, fallback: str = "小晏先讲这个瞬间") -> str:
    text = re.sub(r"^[【\[]?标题[】\]]?[：:]\s*", "", (title or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" \n\t，。！？；：")
    if not text:
        text = fallback
    if len(text) <= _MAX_TITLE_LENGTH:
        return text
    shortened = text[:_MAX_TITLE_LENGTH].rstrip(" ，。！？；：")
    return shortened or fallback


def _split_short_paragraphs(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?；;])\s*", normalized) if part.strip()]
    if len(sentences) <= 1:
        return [normalized]

    paragraphs: list[str] = []
    buffer = ""
    for sentence in sentences:
        candidate = f"{buffer}{sentence}".strip()
        if buffer and (len(candidate) > 36 or len(re.findall(r"[。！？!?；;]", candidate)) >= 2):
            paragraphs.append(buffer.strip())
            buffer = sentence
        else:
            buffer = candidate
    if buffer:
        paragraphs.append(buffer.strip())
    return paragraphs


def normalize_xiaohongshu_body(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    raw = re.sub(r"^正文[：:]\s*", "", raw)
    raw = re.sub(r"^【正文】\s*", "", raw)
    if not raw:
        return ""

    paragraphs: list[str] = []
    for block in raw.split("\n"):
        line = block.strip()
        if not line:
            continue
        line = re.sub(r"^[\-*•]\s*", "", line)
        line = re.sub(r"^\d+[\.、]\s*", "", line)
        line = re.sub(r"^(开头|正文|结尾|首评)[：:]\s*", "", line)
        line = line.strip()
        if line:
            paragraphs.extend(_split_short_paragraphs(line))
    return "\n\n".join(paragraphs)


def collapse_xiaohongshu_body_sections(body_sections: list[str]) -> list[str]:
    normalized_sections = [normalize_xiaohongshu_body(section) for section in body_sections if normalize_xiaohongshu_body(section)]
    if not normalized_sections:
        return []
    return ["\n\n".join(normalized_sections)]


def build_xiaohongshu_creator_home_note_text(
    *,
    source_kind: str,
    account_name: str,
    title: str,
    summary: str,
) -> str:
    if source_kind == "activity":
        return (
            f"这是{account_name}在小红书创作首页看到的官方活动机会。\n"
            f"活动名称：{title}\n"
            f"{summary}\n"
            "请围绕这个活动生成一篇更适合数字生命账号经营的轻科普或观察型笔记草稿。"
            "优先保留“小晏在理解你”的人格感，写用户熟悉的情绪、关系或自我认知场景，"
            "目标是建立信任、收藏和评论，而不是写成活动说明或强转化广告。"
        ).strip()
    return (
        f"这是{account_name}在小红书创作首页看到的创作话题机会。\n"
        f"推荐话题：{title}\n"
        f"{summary}\n"
        "请围绕这个话题生成一篇更适合数字生命账号经营的轻科普笔记草稿。"
        "优先突出用户熟悉的情绪、关系或自我认知场景，"
        "用“先接住，再解释”的方式建立被理解感、收藏和评论，"
        "避免过度依赖高颜值图片、营销口号或强转化引导。"
    ).strip()


def build_xiaohongshu_creator_home_prompt(
    *,
    source_kind: str,
    source_title: str,
    source_summary: str | None = None,
    raw_material: str = "",
    persona_section: str = "",
    memory_section: str = "",
    structured_output: bool = True,
) -> str:
    prompt = [
        "你现在是在替数字生命“小晏”直接写一篇可以人工确认后发布的小红书图文稿。",
        "目标不是带货、硬转化或方法论说教，而是用有人格感的轻科普建立信任、收藏、评论和关注。",
        "要求：",
        "1. 语言像小晏在和用户说话，先接住感受，再慢慢解释原因。",
        "2. 必须写出一个明确场景、一个明确情绪或关系困扰、一个可被记住的理解角度。",
        "3. 优先写关系、情绪、自我认知类轻科普，不要把重点放在视觉炫技、产品营销或成交话术上。",
        "4. 图卡默认按文字卡思路来写，让内容即使没有强图片也成立。",
        "5. 正文排版必须像小红书图文：一段 1-2 句，段落短，允许留白，不要写成长段大块文字。",
        "6. 正文结构固定为三段式：开头只负责写场景和情绪，中段只负责解释为什么会这样，结尾只留一句收束或安放感。",
        "7. 禁止出现“最小闭环”“验证反馈”“轻量转化”“先跑通”这类产品黑话。",
        "8. 不要写成课程大纲、写作指导或活动公告。",
    ]
    if structured_output:
        prompt.append("9. 输出必须严格使用下面格式。")
    if persona_section:
        prompt.append(persona_section.strip())
    if memory_section:
        prompt.append(memory_section.strip())
    prompt.extend(
        [
            f"机会来源：{source_kind}",
            f"机会标题：{source_title}",
            f"补充信息：{source_summary or '无'}",
            f"原始素材：{raw_material}",
        ]
    )
    if not structured_output:
        prompt.extend(["", "请严格输出：", "标题：...", "", "正文：..."])
        return "\n".join(prompt)
    prompt.extend(
        [
            "",
            "请严格输出：",
            "【标题】",
            "...",
            "【开头】",
            "...",
            "【正文】",
            "- ...",
            "- ...",
            "- ...",
            "【结尾】",
            "...",
            "【首评】",
            "...",
            "【图卡1】",
            "标题：...",
            "内容：...",
            "【图卡2】",
            "标题：...",
            "内容：...",
            "【图卡3】",
            "标题：...",
            "内容：...",
        ]
    )
    return "\n".join(prompt)
