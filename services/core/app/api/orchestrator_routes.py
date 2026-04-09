from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import get_chat_gateway, get_orchestrator_conversation_service, get_orchestrator_service
from app.domain.models import (
    OrchestratorDelegateCompletionPayload,
    OrchestratorSchedulerSnapshot,
    OrchestratorSession,
    OrchestratorTask,
)
from app.llm.gateway import ChatGateway
from app.orchestrator.conversation_models import OrchestratorChatSubmissionResult, OrchestratorMessage
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.service import OrchestratorService


class OrchestratorSessionCreateRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    project_path: str = Field(..., min_length=1)


class OrchestratorRejectPlanRequest(BaseModel):
    reason: str | None = None


class OrchestratorDirectiveRequest(BaseModel):
    message: str = Field(..., min_length=1)


class OrchestratorChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


def build_orchestrator_router() -> APIRouter:
    router = APIRouter()

    def _hub(request: Request):
        return getattr(request.app.state, "realtime_hub", None)

    def _raise_client_error(error: ValueError) -> None:
        detail = str(error)
        status_code = 409
        if any(token in detail for token in ["not found"]):
            status_code = 404
        elif any(token in detail for token in ["required", "must", "not ready", "no imported", "project_path"]):
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail) from error

    def _is_approval_message(message: str) -> bool:
        return any(token in message for token in ["批准计划", "审批通过", "开始执行", "开工", "批准并开工"])

    def _is_reject_message(message: str) -> bool:
        return any(token in message for token in ["拒绝计划", "否决计划", "重新规划", "驳回计划"])

    def _is_cancel_message(message: str) -> bool:
        return any(token in message for token in ["退出主控", "取消主控", "结束主控", "取消会话"])

    def _is_resume_message(message: str) -> bool:
        return any(token in message for token in ["恢复主控", "继续推进", "重派", "恢复会话", "重跑验收"])

    def _is_generate_plan_message(message: str) -> bool:
        return any(token in message for token in ["生成计划", "修改计划", "重新计划", "给我一个计划", "制定计划"])

    def _handle_command_message(
        *,
        session_id: str,
        message: str,
        request: Request,
        orchestrator_service: OrchestratorService,
        conversation_service: OrchestratorConversationService,
        save_user_message: bool,
    ) -> tuple[OrchestratorSession | None, str | None]:
        normalized = message.strip()
        lowered = normalized.lower()
        if save_user_message:
            conversation_service.append_user_message(session_id, normalized, hub=_hub(request))

        try:
            if _is_approval_message(normalized):
                session = orchestrator_service.approve_plan(session_id, hub=_hub(request))
                return session, "好的，计划已批准，我会开始推进当前主控任务。"
            if _is_reject_message(normalized):
                session = orchestrator_service.reject_plan(session_id, reason=normalized, hub=_hub(request))
                return session, "我已经把这次计划退回到待重规划状态。"
            if _is_cancel_message(normalized):
                session = orchestrator_service.cancel(session_id, hub=_hub(request))
                return session, "这次主控会话已经退出。"
            if _is_resume_message(normalized):
                session = orchestrator_service.resume_session(session_id, hub=_hub(request))
                return session, "我已经把主控会话恢复到调度队列。"
            if _is_generate_plan_message(normalized):
                session = orchestrator_service.generate_plan(session_id, hub=_hub(request))
                return session, "新的主控计划已经生成，我把任务拆解和待审批信息贴到消息流里了。"
            if any(token in lowered for token in ["scope", "验收", "优先级", "范围", "acceptance"]):
                session = orchestrator_service.apply_directive(session_id, normalized, hub=_hub(request))
                return session, session.summary or "主控边界已经更新。"
        except ValueError as error:
            raise error

        return None, None

    @router.post("/orchestrator/sessions", response_model=OrchestratorSession)
    def create_session(
        request_body: OrchestratorSessionCreateRequest,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.create_session(request_body.goal, request_body.project_path, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.get("/orchestrator/sessions", response_model=list[OrchestratorSession])
    def list_sessions(
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> list[OrchestratorSession]:
        return service.list_sessions()

    @router.post("/orchestrator/sessions/{session_id}/activate", response_model=OrchestratorSession)
    def activate_session(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.activate_session(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/plan", response_model=OrchestratorSession)
    def generate_plan(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.generate_plan(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/approve-plan", response_model=OrchestratorSession)
    def approve_plan(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.approve_plan(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/reject-plan", response_model=OrchestratorSession)
    def reject_plan(
        session_id: str,
        request: Request,
        request_body: OrchestratorRejectPlanRequest | None = None,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.reject_plan(
                session_id,
                reason=request_body.reason if request_body is not None else None,
                hub=_hub(request),
            )
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/dispatch", response_model=OrchestratorSession)
    def dispatch_session(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.dispatch(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.get("/orchestrator/scheduler", response_model=OrchestratorSchedulerSnapshot)
    def get_scheduler_snapshot(
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSchedulerSnapshot:
        return service.get_scheduler_snapshot()

    @router.post("/orchestrator/scheduler/tick", response_model=OrchestratorSchedulerSnapshot)
    def run_scheduler_tick(
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSchedulerSnapshot:
        return service.run_scheduler_tick(hub=_hub(request))

    @router.get("/orchestrator/sessions/{session_id}", response_model=OrchestratorSession)
    def get_session(
        session_id: str,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.get_session(session_id)
        except ValueError as error:
            _raise_client_error(error)

    @router.get("/orchestrator/sessions/{session_id}/tasks", response_model=list[OrchestratorTask])
    def list_tasks(
        session_id: str,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> list[OrchestratorTask]:
        try:
            return service.list_tasks(session_id)
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/cancel", response_model=OrchestratorSession)
    def cancel_session(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.cancel(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/resume", response_model=OrchestratorSession)
    def resume_session(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.resume_session(session_id, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/directive", response_model=OrchestratorSession)
    def apply_directive(
        session_id: str,
        request_body: OrchestratorDirectiveRequest,
        request: Request,
        conversation_service: OrchestratorConversationService = Depends(get_orchestrator_conversation_service),
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            session, reply = _handle_command_message(
                session_id=session_id,
                message=request_body.message,
                request=request,
                orchestrator_service=service,
                conversation_service=conversation_service,
                save_user_message=True,
            )
            if session is None:
                raise ValueError("unsupported orchestrator directive")
            if reply:
                conversation_service.append_assistant_message(session, reply, hub=_hub(request))
            return session
        except ValueError as error:
            _raise_client_error(error)

    @router.get("/orchestrator/sessions/{session_id}/messages", response_model=list[OrchestratorMessage])
    def list_messages(
        session_id: str,
        service: OrchestratorService = Depends(get_orchestrator_service),
        conversation_service: OrchestratorConversationService = Depends(get_orchestrator_conversation_service),
    ) -> list[OrchestratorMessage]:
        try:
            service.get_session(session_id)
            return conversation_service.list_messages(session_id)
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/sessions/{session_id}/chat", response_model=OrchestratorChatSubmissionResult)
    def chat_with_orchestrator(
        session_id: str,
        request_body: OrchestratorChatRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        service: OrchestratorService = Depends(get_orchestrator_service),
        conversation_service: OrchestratorConversationService = Depends(get_orchestrator_conversation_service),
    ) -> OrchestratorChatSubmissionResult:
        try:
            session = service.get_session(session_id)
            user_message = request_body.message.strip()
            if not user_message:
                raise ValueError("message is required")
            conversation_service.append_user_message(session_id, user_message, hub=_hub(request))

            handled_session, reply = _handle_command_message(
                session_id=session_id,
                message=user_message,
                request=request,
                orchestrator_service=service,
                conversation_service=conversation_service,
                save_user_message=False,
            )
            if handled_session is not None and reply is not None:
                assistant_message = conversation_service.append_assistant_message(
                    handled_session,
                    reply,
                    hub=_hub(request),
                )
                return OrchestratorChatSubmissionResult(
                    session_id=handled_session.session_id,
                    assistant_message_id=assistant_message.message_id,
                )

            return conversation_service.stream_assistant_reply(
                session,
                user_message,
                gateway=gateway,
                hub=_hub(request),
            )
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/delegates/complete", response_model=OrchestratorSession)
    def complete_delegate(
        payload: OrchestratorDelegateCompletionPayload,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.complete_delegate(payload, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    return router
