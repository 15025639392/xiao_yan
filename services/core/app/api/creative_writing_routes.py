from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_creative_writing_service, get_optional_chat_gateway
from app.creative_writing.models import NovelCharacter
from app.creative_writing.service import CreativeWritingService
from app.llm.gateway import ChatGateway


class CreateNovelProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    premise: str = Field(min_length=1)
    tone: str | None = None
    characters: list[NovelCharacter] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)


class WriteNovelFragmentRequest(BaseModel):
    intention: str | None = None
    content: str | None = None
    summary: str = ""


class ExecuteNovelWritingSessionRequest(BaseModel):
    content: str | None = None
    summary: str = ""


class AdvanceNovelChapterRequest(BaseModel):
    summary: str = Field(min_length=1)
    title: str = ""


class UpdateNovelHabitStateRequest(BaseModel):
    attachment_reason: str | None = None
    last_pause: str | None = None
    next_intention: str | None = None
    cadence_note: str | None = None


def build_creative_writing_router() -> APIRouter:
    router = APIRouter(prefix="/creative-writing", tags=["creative-writing"])

    @router.get("/projects")
    def list_projects(
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        return {"projects": [project.model_dump(mode="json") for project in service.list_projects()]}

    @router.get("/impulses")
    def get_writing_impulses(
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        return service.get_writing_impulse_report().model_dump(mode="json")

    @router.get("/session-suggestion")
    def get_session_suggestion(
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        suggestion = service.get_session_suggestion()
        return {"suggestion": suggestion.model_dump(mode="json") if suggestion else None}

    @router.get("/sessions")
    def list_sessions(
        project_id: str | None = None,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        try:
            sessions = service.list_sessions(project_id=project_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        return {"sessions": [session.model_dump(mode="json") for session in sessions]}

    @router.post("/sessions")
    def create_pending_session(
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        session = service.create_pending_session()
        return {"session": session.model_dump(mode="json") if session else None}

    @router.post("/sessions/{session_id}/execute")
    def execute_session(
        session_id: str,
        payload: ExecuteNovelWritingSessionRequest,
        service: CreativeWritingService = Depends(get_creative_writing_service),
        gateway: ChatGateway | None = Depends(get_optional_chat_gateway),
    ) -> dict:
        try:
            session, fragment = service.execute_session(
                session_id=session_id,
                gateway=gateway,
                content=payload.content,
                summary=payload.summary,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="writing session not found") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "session": session.model_dump(mode="json"),
            "fragment": fragment.model_dump(mode="json"),
        }

    @router.post("/projects")
    def create_project(
        payload: CreateNovelProjectRequest,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        project = service.create_project(
            title=payload.title,
            premise=payload.premise,
            tone=payload.tone,
            characters=payload.characters,
            outline=payload.outline,
        )
        return {"project": project.model_dump(mode="json")}

    @router.get("/projects/{project_id}")
    def get_project(
        project_id: str,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        project = service.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="novel project not found")
        return {
            "project": project.model_dump(mode="json"),
            "fragments": [fragment.model_dump(mode="json") for fragment in service.get_project_fragments(project_id)],
            "chapter_summaries": [
                summary.model_dump(mode="json") for summary in service.get_chapter_summaries(project_id)
            ],
        }

    @router.get("/projects/{project_id}/context")
    def get_writing_context(
        project_id: str,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        try:
            context = service.get_writing_context(project_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        return {"context": context.model_dump(mode="json")}

    @router.post("/projects/{project_id}/sessions")
    def create_project_pending_session(
        project_id: str,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        try:
            session = service.create_pending_session(project_id=project_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        return {"session": session.model_dump(mode="json") if session else None}

    @router.patch("/projects/{project_id}/habit")
    def update_habit_state(
        project_id: str,
        payload: UpdateNovelHabitStateRequest,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        try:
            project = service.update_habit_state(
                project_id=project_id,
                attachment_reason=payload.attachment_reason,
                last_pause=payload.last_pause,
                next_intention=payload.next_intention,
                cadence_note=payload.cadence_note,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        return {"project": project.model_dump(mode="json")}

    @router.post("/projects/{project_id}/fragments")
    def write_fragment(
        project_id: str,
        payload: WriteNovelFragmentRequest,
        service: CreativeWritingService = Depends(get_creative_writing_service),
        gateway: ChatGateway | None = Depends(get_optional_chat_gateway),
    ) -> dict:
        try:
            fragment = service.write_fragment(
                project_id=project_id,
                gateway=gateway,
                intention=payload.intention,
                content=payload.content,
                summary=payload.summary,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"fragment": fragment.model_dump(mode="json")}

    @router.post("/projects/{project_id}/chapters/advance")
    def advance_chapter(
        project_id: str,
        payload: AdvanceNovelChapterRequest,
        service: CreativeWritingService = Depends(get_creative_writing_service),
    ) -> dict:
        try:
            project, chapter_summary = service.advance_chapter(
                project_id=project_id,
                summary=payload.summary,
                title=payload.title,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="novel project not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "project": project.model_dump(mode="json"),
            "chapter_summary": chapter_summary.model_dump(mode="json"),
        }

    return router
