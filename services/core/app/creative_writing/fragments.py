from __future__ import annotations

from uuid import uuid4

from app.creative_writing.models import NovelFragment, NovelFragmentDigest, NovelHabitState, NovelProject, utc_now
from app.creative_writing.repository import CreativeWritingRepository


def save_project_fragment(
    *,
    repository: CreativeWritingRepository,
    project: NovelProject,
    chapter_index: int,
    content: str,
    intention: str | None,
    summary: str,
    digest: NovelFragmentDigest | None = None,
) -> NovelFragment:
    final_summary = summary.strip() or (digest.summary if digest else "")
    sequence = repository.next_fragment_sequence(project, chapter_index)
    fragment = NovelFragment(
        id=uuid4().hex[:12],
        project_id=project.id,
        chapter_index=chapter_index,
        sequence=sequence,
        content=content,
        summary=final_summary,
        digest=digest,
        file_path=repository.fragment_relative_path(
            project,
            chapter_index,
            sequence,
        ),
    )
    saved = repository.save_fragment(project, fragment)
    habit_state = habit_after_fragment(project.habit_state, intention, final_summary, digest)
    repository.save_project(project.model_copy(update={"habit_state": habit_state, "updated_at": utc_now()}))
    return saved


def habit_after_fragment(
    habit_state: NovelHabitState,
    intention: str | None,
    summary: str,
    digest: NovelFragmentDigest | None = None,
) -> NovelHabitState:
    updates: dict[str, str] = {}
    if intention:
        updates["last_pause"] = f"刚写过：{intention.strip()}"
    if digest and digest.next_intention:
        updates["next_intention"] = digest.next_intention.strip()
    elif summary and not habit_state.next_intention:
        updates["next_intention"] = f"承接上一段：{summary.strip()}"
    if not updates:
        updates["last_pause"] = "刚完成了一个正文片段。"
    return habit_state.model_copy(update={**updates, "updated_at": utc_now()})
