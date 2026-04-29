from __future__ import annotations

from collections.abc import Callable

from app.creative_writing.models import (
    BeingWritingContext,
    CreativeWritingImpulseReport,
    NovelChapterSummary,
    NovelFragment,
    NovelProject,
    NovelWritingImpulse,
)


FragmentLoader = Callable[[NovelProject], list[NovelFragment]]
ChapterSummaryLoader = Callable[[NovelProject], list[NovelChapterSummary]]


def build_impulse_report(
    projects: list[NovelProject],
    *,
    load_current_fragments: FragmentLoader,
    load_chapter_summaries: ChapterSummaryLoader,
    being_context: BeingWritingContext | None = None,
) -> CreativeWritingImpulseReport:
    impulses = [
        build_project_impulse(
            project,
            current_fragments=load_current_fragments(project),
            chapter_summaries=load_chapter_summaries(project),
            being_context=being_context,
        )
        for project in projects
    ]
    ranked = sorted(impulses, key=lambda item: item.score, reverse=True)
    recommended = next((item.project_id for item in ranked if item.score > 0), None)
    return CreativeWritingImpulseReport(
        recommended_project_id=recommended,
        impulses=ranked,
        being_context=being_context,
    )


def build_project_impulse(
    project: NovelProject,
    *,
    current_fragments: list[NovelFragment],
    chapter_summaries: list[NovelChapterSummary],
    being_context: BeingWritingContext | None = None,
) -> NovelWritingImpulse:
    if project.status == "finished":
        return NovelWritingImpulse(
            project_id=project.id,
            title=project.title,
            score=0,
            reasons=["这部小说已经完成，不建议继续续写。"],
            next_intention=project.habit_state.next_intention,
            suggested_action="回看或整理成稿",
        )

    reasons: list[str] = []
    score = 10
    if project.status == "paused":
        score = 5
        reasons.append("项目处于暂停状态，只适合轻轻回看。")
    else:
        reasons.append("项目仍在起草中。")

    if project.habit_state.attachment_reason:
        score += 30
        reasons.append(f"牵挂清楚：{project.habit_state.attachment_reason}")
    if project.habit_state.next_intention:
        score += 30
        reasons.append(f"下一步明确：{project.habit_state.next_intention}")
    if project.habit_state.last_pause:
        score += 15
        reasons.append(f"停顿位置可接：{project.habit_state.last_pause}")

    if current_fragments:
        score += 10
        reasons.append("当前章节已有片段，可以顺着余温继续。")
    elif chapter_summaries:
        score += 8
        reasons.append("前章摘要已收束，可以开启新章。")
    else:
        reasons.append("还没有正文片段，适合先写一个开场。")

    score = apply_being_context(score, reasons, being_context)
    suggested_action = (
        "继续写一个短片段"
        if project.habit_state.next_intention or current_fragments
        else "先写一个开场片段"
    )
    return NovelWritingImpulse(
        project_id=project.id,
        title=project.title,
        score=score,
        reasons=reasons,
        next_intention=project.habit_state.next_intention,
        suggested_action=suggested_action,
    )


def apply_being_context(
    score: int,
    reasons: list[str],
    context: BeingWritingContext | None,
) -> int:
    if context is None:
        return score

    if context.energy == "low":
        score -= 8
        reasons.append("此刻能量偏低，更适合轻轻写一个短片段。")
    elif context.energy == "high":
        score += 6
        reasons.append("此刻能量较高，可以承接更清楚的创作动作。")

    if context.mood == "engaged":
        score += 6
        reasons.append("世界状态显示她正比较投入。")
    elif context.mood == "tired":
        score -= 4
        reasons.append("世界状态偏疲惫，写作冲动需要放轻。")

    if context.primary_emotion in {"engaged", "joy", "proud", "grateful"}:
        score += 8
        reasons.append(f"当前情绪是 {context.primary_emotion}，更容易进入创作。")
    elif context.primary_emotion in {"fear", "anger", "frustrated"}:
        score -= 6
        reasons.append(f"当前情绪是 {context.primary_emotion}，不适合强推写作。")
    elif context.primary_emotion in {"sadness", "lonely"}:
        score += 3
        reasons.append(f"当前情绪是 {context.primary_emotion}，适合写更内向的一小段。")

    if context.arousal > 0.85:
        score -= 5
        reasons.append("此刻唤醒度过高，写作建议保持低压。")

    return max(score, 0)
