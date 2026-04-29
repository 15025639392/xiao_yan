from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.creative_writing.digestion import digest_fragment
from app.creative_writing.fragments import save_project_fragment
from app.creative_writing.impulses import build_project_impulse
from app.creative_writing.models import (
    BeingWritingContext,
    NovelFragment,
    NovelProject,
    NovelWritingContext,
    NovelWritingSession,
    NovelWritingSessionSuggestion,
    utc_now,
)
from app.creative_writing.repository import CreativeWritingRepository
from app.llm.gateway import ChatGateway


FragmentGenerator = Callable[[NovelProject, ChatGateway | None, str | None, NovelWritingContext], str]


def build_session_suggestion_for_project(
    repository: CreativeWritingRepository,
    project_id: str,
    *,
    being_context: BeingWritingContext | None = None,
) -> NovelWritingSessionSuggestion | None:
    project = repository.get_project(project_id)
    if project is None:
        raise KeyError(project_id)
    impulse = build_project_impulse(
        project,
        current_fragments=repository.list_fragments(project, chapter_index=project.current_chapter_index),
        chapter_summaries=repository.list_chapter_summaries(project),
        being_context=being_context,
    )
    if impulse.score <= 0:
        return None
    return NovelWritingSessionSuggestion(
        project_id=project.id,
        title=project.title,
        intention=impulse.next_intention or impulse.suggested_action,
        suggested_action=impulse.suggested_action,
        reasons=impulse.reasons,
        context=repository.build_writing_context(project),
    )


def create_session_from_suggestion(
    repository: CreativeWritingRepository,
    suggestion: NovelWritingSessionSuggestion,
) -> NovelWritingSession | None:
    project = repository.get_project(suggestion.project_id)
    if project is None:
        return None
    session = NovelWritingSession(
        id=uuid4().hex[:12],
        project_id=suggestion.project_id,
        title=suggestion.title,
        intention=suggestion.intention,
        suggested_action=suggestion.suggested_action,
        reasons=suggestion.reasons,
        context=suggestion.context,
    )
    return repository.save_session(project, session)


def execute_pending_session(
    *,
    repository: CreativeWritingRepository,
    session_id: str,
    gateway: ChatGateway | None,
    content: str | None,
    summary: str,
    generate_fragment: FragmentGenerator,
) -> tuple[NovelWritingSession, NovelFragment]:
    session = repository.get_session(session_id)
    if session is None:
        raise KeyError(session_id)
    if session.status != "pending":
        raise ValueError("writing session is not pending")

    project = repository.get_project(session.project_id)
    if project is None:
        raise KeyError(session.project_id)
    if project.current_chapter_index != session.context.chapter_index:
        raise ValueError("writing session context no longer matches the current chapter")

    fragment_content = content.strip() if content else generate_fragment(
        project,
        gateway,
        session.intention,
        session.context,
    )
    digest = None
    if not summary.strip():
        digest = digest_fragment(
            gateway=gateway,
            project=project,
            content=fragment_content,
            intention=session.intention,
            context=session.context,
        )
    fragment = save_project_fragment(
        repository=repository,
        project=project,
        chapter_index=session.context.chapter_index,
        content=fragment_content,
        intention=session.intention,
        summary=summary,
        digest=digest,
    )
    completed = session.model_copy(
        update={
            "status": "completed",
            "completed_fragment_id": fragment.id,
            "updated_at": utc_now(),
        }
    )
    return repository.save_session(project, completed), fragment
