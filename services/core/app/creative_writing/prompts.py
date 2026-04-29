from __future__ import annotations

from app.creative_writing.models import NovelProject, NovelWritingContext


def build_writing_instructions(persona_prompt: str) -> str:
    return (
        f"{persona_prompt}\n\n"
        "你正在写属于你自己的小说。写作是一种人格驱动的创作习惯，"
        "不是平台任务，也不是为了批量生产内容。\n"
        "保持小晏的审美、情绪节奏和人物偏好。只写本次片段，不要总结、"
        "不要解释创作思路、不要加标题。"
    )


def build_fragment_prompt(
    project: NovelProject,
    intention: str | None,
    context: NovelWritingContext | None = None,
) -> str:
    outline = "\n".join(f"- {item}" for item in project.outline) or "- 暂无固定大纲，允许从人物状态自然生长。"
    characters = "\n".join(
        f"- {item.name}：{item.role}；想要：{item.desire}" for item in project.characters
    ) or "- 角色仍在形成中。"
    continuity = _format_continuity(context)
    return (
        f"小说标题：{project.title}\n"
        f"核心前提：{project.premise}\n"
        f"语气：{project.tone}\n"
        f"创作牵挂：{project.habit_state.attachment_reason or project.habit_note}\n"
        f"上次停顿：{project.habit_state.last_pause or '暂无明确停顿记录。'}\n"
        f"下次意向：{project.habit_state.next_intention or '暂无明确意向。'}\n"
        f"节律备注：{project.habit_state.cadence_note}\n"
        f"当前章节：第 {project.current_chapter_index} 章\n"
        f"角色：\n{characters}\n\n"
        f"大纲：\n{outline}\n\n"
        f"{continuity}"
        f"本次写作意图：{intention or '顺着上一段的情绪继续写一个短片段。'}\n\n"
        "请写 800 到 1500 字左右的中文小说正文片段。"
    )


def _format_continuity(context: NovelWritingContext | None) -> str:
    if context is None or (
        not context.previous_chapter_summaries
        and not context.recent_summaries
        and not context.recent_excerpt
    ):
        return ""
    previous_chapters = "\n".join(f"- {item}" for item in context.previous_chapter_summaries) or "- 暂无前章摘要。"
    summaries = "\n".join(f"- {item}" for item in context.recent_summaries) or "- 暂无摘要。"
    return (
        "上一段连续性资料：\n"
        f"前章摘要：\n{previous_chapters}\n\n"
        f"近期摘要：\n{summaries}\n\n"
        f"最近正文尾部：\n{context.recent_excerpt or '暂无正文。'}\n\n"
        "请自然承接这些内容，不要重述摘要。\n\n"
    )
