from __future__ import annotations

from uuid import uuid4

from app.creative_writing.models import (
    CreativeWritingImpulseReport,
    NovelChapterSummary,
    NovelCharacter,
    NovelFragment,
    NovelProject,
    NovelWritingSession,
    NovelWritingSessionSuggestion,
    NovelWritingContext,
    utc_now,
)
from app.creative_writing.being_context import build_being_writing_context
from app.creative_writing.chapters import advance_project_chapter
from app.creative_writing.digestion import digest_fragment
from app.creative_writing.fragments import save_project_fragment
from app.creative_writing.habits import update_project_habit_state
from app.creative_writing.impulses import build_impulse_report, build_project_impulse
from app.creative_writing.prompts import build_fragment_prompt, build_writing_instructions
from app.creative_writing.repository import CreativeWritingRepository, safe_folder_name
from app.creative_writing.sessions import (
    build_session_suggestion_for_project,
    create_session_from_suggestion,
    execute_pending_session,
)
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage
from app.persona.service import PersonaService
from app.world.repository import WorldRepository


class CreativeWritingService:
    def __init__(
        self,
        repository: CreativeWritingRepository,
        persona_service: PersonaService,
        world_repository: WorldRepository | None = None,
    ) -> None:
        self.repository = repository
        self.persona_service = persona_service
        self.world_repository = world_repository

    def create_project(
        self,
        *,
        title: str,
        premise: str,
        tone: str | None = None,
        characters: list[NovelCharacter] | None = None,
        outline: list[str] | None = None,
    ) -> NovelProject:
        project_id = uuid4().hex[:12]
        project = NovelProject(
            id=project_id,
            title=title.strip(),
            premise=premise.strip(),
            tone=(tone or NovelProject.model_fields["tone"].default).strip(),
            characters=characters or [],
            outline=outline or [],
            folder_name=safe_folder_name(project_id, title),
        )
        return self.repository.save_project(project)

    def list_projects(self) -> list[NovelProject]:
        return self.repository.list_projects()

    def get_project(self, project_id: str) -> NovelProject | None:
        return self.repository.get_project(project_id)

    def get_writing_impulse_report(self) -> CreativeWritingImpulseReport:
        return build_impulse_report(
            self.repository.list_projects(),
            load_current_fragments=lambda project: self.repository.list_fragments(
                project,
                chapter_index=project.current_chapter_index,
            ),
            load_chapter_summaries=self.repository.list_chapter_summaries,
            being_context=self._build_being_context(),
        )

    def get_session_suggestion(self) -> NovelWritingSessionSuggestion | None:
        report = self.get_writing_impulse_report()
        if report.recommended_project_id is None:
            return None
        project = self.repository.get_project(report.recommended_project_id)
        if project is None:
            return None
        impulse = next(
            item for item in report.impulses
            if item.project_id == report.recommended_project_id
        )
        intention = impulse.next_intention or impulse.suggested_action
        return NovelWritingSessionSuggestion(
            project_id=project.id,
            title=project.title,
            intention=intention,
            suggested_action=impulse.suggested_action,
            reasons=impulse.reasons,
            context=self.repository.build_writing_context(project),
        )

    def create_pending_session(self, project_id: str | None = None) -> NovelWritingSession | None:
        suggestion = build_session_suggestion_for_project(
            self.repository,
            project_id,
            being_context=self._build_being_context(),
        ) if project_id is not None else self.get_session_suggestion()
        if suggestion is None:
            return None
        return create_session_from_suggestion(self.repository, suggestion)

    def list_sessions(self, project_id: str | None = None) -> list[NovelWritingSession]:
        if project_id is None:
            return self.repository.list_sessions()
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return self.repository.list_sessions(project)

    def execute_session(
        self,
        *,
        session_id: str,
        gateway: ChatGateway | None,
        content: str | None = None,
        summary: str = "",
    ) -> tuple[NovelWritingSession, NovelFragment]:
        return execute_pending_session(
            repository=self.repository,
            session_id=session_id,
            gateway=gateway,
            content=content,
            summary=summary,
            generate_fragment=self._generate_fragment,
        )

    def get_project_fragments(self, project_id: str) -> list[NovelFragment]:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return self.repository.list_fragments(project)

    def get_chapter_summaries(self, project_id: str) -> list[NovelChapterSummary]:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return self.repository.list_chapter_summaries(project)

    def get_writing_context(self, project_id: str) -> NovelWritingContext:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return self.repository.build_writing_context(project)

    def update_habit_state(
        self,
        *,
        project_id: str,
        attachment_reason: str | None = None,
        last_pause: str | None = None,
        next_intention: str | None = None,
        cadence_note: str | None = None,
    ) -> NovelProject:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)

        updated_project = update_project_habit_state(
            project,
            attachment_reason=attachment_reason,
            last_pause=last_pause,
            next_intention=next_intention,
            cadence_note=cadence_note,
        )
        return self.repository.save_project(updated_project)

    def advance_chapter(
        self,
        *,
        project_id: str,
        summary: str,
        title: str = "",
    ) -> tuple[NovelProject, NovelChapterSummary]:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return advance_project_chapter(
            repository=self.repository,
            project=project,
            summary=summary,
            title=title,
        )

    def write_fragment(
        self,
        *,
        project_id: str,
        gateway: ChatGateway | None,
        intention: str | None = None,
        content: str | None = None,
        summary: str = "",
    ) -> NovelFragment:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)

        context = self.repository.build_writing_context(project)
        fragment_content = content.strip() if content else self._generate_fragment(project, gateway, intention, context)
        digest = self._digest_written_fragment(
            gateway=gateway,
            project=project,
            content=fragment_content,
            intention=intention,
            context=context,
            summary=summary,
        )
        return save_project_fragment(
            repository=self.repository,
            project=project,
            chapter_index=project.current_chapter_index,
            content=fragment_content,
            intention=intention,
            summary=summary,
            digest=digest,
        )

    def _digest_written_fragment(
        self,
        *,
        gateway: ChatGateway | None,
        project: NovelProject,
        content: str,
        intention: str | None,
        context: NovelWritingContext,
        summary: str,
    ):
        if summary.strip():
            return None
        return digest_fragment(
            gateway=gateway,
            project=project,
            content=content,
            intention=intention,
            context=context,
        )

    def _build_being_context(self):
        return build_being_writing_context(
            persona_service=self.persona_service,
            world_repository=self.world_repository,
        )

    def _generate_fragment(
        self,
        project: NovelProject,
        gateway: ChatGateway | None,
        intention: str | None,
        context: NovelWritingContext,
    ) -> str:
        if gateway is None:
            raise RuntimeError("writing generation requires a configured chat gateway")
        result = gateway.create_response(
            [ChatMessage(role="user", content=build_fragment_prompt(project, intention, context))],
            instructions=build_writing_instructions(self.persona_service.build_system_prompt()),
        )
        return result.output_text.strip()
