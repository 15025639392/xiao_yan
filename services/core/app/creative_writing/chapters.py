from __future__ import annotations

from uuid import uuid4

from app.creative_writing.models import NovelChapterSummary, NovelProject, utc_now
from app.creative_writing.repository import CreativeWritingRepository


def advance_project_chapter(
    *,
    repository: CreativeWritingRepository,
    project: NovelProject,
    summary: str,
    title: str = "",
) -> tuple[NovelProject, NovelChapterSummary]:
    if not summary.strip():
        raise ValueError("chapter summary is required")

    chapter_summary = NovelChapterSummary(
        id=uuid4().hex[:12],
        project_id=project.id,
        chapter_index=project.current_chapter_index,
        title=title.strip(),
        summary=summary.strip(),
        file_path=repository.chapter_summary_relative_path(project, project.current_chapter_index),
    )
    saved_summary = repository.save_chapter_summary(project, chapter_summary)
    updated_project = project.model_copy(
        update={
            "current_chapter_index": project.current_chapter_index + 1,
            "updated_at": utc_now(),
        }
    )
    return repository.save_project(updated_project), saved_summary
