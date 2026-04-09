from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import httpx

from app.domain.models import OrchestratorSchedulerSnapshot, OrchestratorSession, OrchestratorTask, OrchestratorVerification
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage
from app.orchestrator.conversation_models import (
    OrchestratorChatSubmissionResult,
    OrchestratorMessage,
    OrchestratorMessageBlock,
    OrchestratorMessageRole,
    OrchestratorMessageState,
)
from app.orchestrator.conversation_prompt import build_orchestrator_chat_instructions
from app.orchestrator.conversation_repository import OrchestratorConversationRepository
from app.realtime import AppRealtimeHub

SchedulerProvider = Callable[[], OrchestratorSchedulerSnapshot]


class OrchestratorConversationService:
    def __init__(
        self,
        repository: OrchestratorConversationRepository,
        *,
        scheduler_provider: SchedulerProvider,
    ) -> None:
        self._repository = repository
        self._scheduler_provider = scheduler_provider

    def list_messages(self, session_id: str) -> list[OrchestratorMessage]:
        return self._repository.list_messages(session_id)

    def append_user_message(self, session_id: str, message: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorMessage:
        return self._append_message(
            OrchestratorMessage(
                session_id=session_id,
                role=OrchestratorMessageRole.USER,
                blocks=[OrchestratorMessageBlock(type="markdown", text=message.strip())],
            ),
            hub=hub,
        )

    def append_assistant_message(
        self,
        session: OrchestratorSession,
        text: str,
        *,
        blocks: list[OrchestratorMessageBlock] | None = None,
        related_task_id: str | None = None,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorMessage:
        merged_blocks = [OrchestratorMessageBlock(type="markdown", text=text.strip())]
        if blocks:
            merged_blocks.extend(blocks)
        return self._append_message(
            OrchestratorMessage(
                session_id=session.session_id,
                role=OrchestratorMessageRole.ASSISTANT,
                blocks=merged_blocks,
                related_task_id=related_task_id,
            ),
            hub=hub,
        )

    def append_system_event(
        self,
        session: OrchestratorSession,
        *,
        summary: str,
        blocks: list[OrchestratorMessageBlock] | None = None,
        related_task_id: str | None = None,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorMessage:
        merged_blocks = [OrchestratorMessageBlock(type="markdown", text=summary)]
        if blocks:
            merged_blocks.extend(blocks)
        return self._append_message(
            OrchestratorMessage(
                session_id=session.session_id,
                role=OrchestratorMessageRole.SYSTEM,
                blocks=merged_blocks,
                related_task_id=related_task_id,
            ),
            hub=hub,
        )

    def append_session_created(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> None:
        self.append_assistant_message(
            session,
            f"已进入主控模式，我会围绕 `{session.project_name}` 持续推进这次项目编排。",
            blocks=[self.build_session_status_block(session)],
            hub=hub,
        )

    def append_plan_generated(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> None:
        if session.plan is None:
            return
        self.append_assistant_message(
            session,
            "主控计划已经整理好了。我先把任务拆解和完成标准摆出来，等你拍板后再正式开工。",
            blocks=[
                OrchestratorMessageBlock(type="plan_card", plan=session.plan),
                OrchestratorMessageBlock(
                    type="approval_card",
                    summary="计划待审批",
                    details={
                        "status": session.status.value,
                        "can_approve": session.status.value == "pending_plan_approval",
                    },
                ),
            ],
            hub=hub,
        )

    def append_plan_approved(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> None:
        self.append_system_event(
            session,
            summary="计划级审批已通过，主控会按依赖关系开始派发任务。",
            blocks=[self.build_session_status_block(session)],
            hub=hub,
        )

    def append_plan_rejected(
        self,
        session: OrchestratorSession,
        reason: str | None = None,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> None:
        self.append_system_event(
            session,
            summary=reason or session.summary or "计划已被拒绝，等待重新规划。",
            blocks=[self.build_session_status_block(session)],
            hub=hub,
        )

    def append_directive_applied(
        self,
        session: OrchestratorSession,
        directive: str,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> None:
        self.append_system_event(
            session,
            summary=session.summary or f"已应用主控指令：{directive}",
            blocks=[
                OrchestratorMessageBlock(
                    type="directive_card",
                    summary=session.summary or directive,
                    details={"directive": directive},
                ),
                self.build_session_status_block(session),
            ],
            hub=hub,
        )

    def append_task_update(
        self,
        session: OrchestratorSession,
        task: OrchestratorTask,
        *,
        phase: str,
        hub: AppRealtimeHub | None = None,
    ) -> None:
        summary = task.result_summary or task.error or task.title
        self.append_system_event(
            session,
            summary=f"{phase}：{summary}",
            blocks=[OrchestratorMessageBlock(type="task_card", task=task), self.build_session_status_block(session)],
            related_task_id=task.task_id,
            hub=hub,
        )

    def append_verification_completed(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> None:
        if session.verification is None:
            return
        blocks = [self.build_verification_block(session.verification)]
        if session.summary:
            blocks.append(OrchestratorMessageBlock(type="summary_card", summary=session.summary))
        blocks.append(self.build_session_status_block(session))
        self.append_system_event(
            session,
            summary=session.summary or "统一验收已完成。",
            blocks=blocks,
            hub=hub,
        )

    def append_session_cancelled(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> None:
        self.append_system_event(
            session,
            summary=session.summary or "主控会话已取消。",
            blocks=[self.build_session_status_block(session)],
            hub=hub,
        )

    def build_session_status_block(self, session: OrchestratorSession) -> OrchestratorMessageBlock:
        coordination = session.coordination
        return OrchestratorMessageBlock(
            type="session_status_card",
            summary=coordination.waiting_reason if coordination is not None else session.summary,
            session=session,
            details={
                "status": session.status.value,
                "coordination_mode": None if coordination is None else coordination.mode.value,
                "queue_position": None if coordination is None else coordination.queue_position,
                "dispatch_slot": None if coordination is None else coordination.dispatch_slot,
                "preempted_by_session_id": None if coordination is None else coordination.preempted_by_session_id,
            },
        )

    def build_verification_block(self, verification: OrchestratorVerification) -> OrchestratorMessageBlock:
        return OrchestratorMessageBlock(
            type="verification_card",
            verification=verification,
            summary=verification.summary,
        )

    def stream_assistant_reply(
        self,
        session: OrchestratorSession,
        user_message: str,
        *,
        gateway: ChatGateway,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorChatSubmissionResult:
        assistant_message = OrchestratorMessage(
            session_id=session.session_id,
            role=OrchestratorMessageRole.ASSISTANT,
            blocks=[OrchestratorMessageBlock(type="markdown", text="")],
            state=OrchestratorMessageState.STREAMING,
        )
        saved = self._append_message(assistant_message, hub=hub)
        instructions = build_orchestrator_chat_instructions(
            session,
            self._scheduler_provider(),
            user_message,
        )
        messages = self._build_context_messages(session.session_id, user_message)

        response_id: str | None = None
        output_text = ""
        started = False

        try:
            for event in gateway.stream_response(messages, instructions=instructions):
                event_type = event["type"]
                if event_type == "response_started":
                    response_id = event.get("response_id") or response_id
                    if hub is not None and not started:
                        hub.publish_orchestrator_message_started(
                            session_id=session.session_id,
                            assistant_message_id=saved.message_id,
                            response_id=response_id,
                        )
                        started = True
                    continue

                if event_type == "text_delta":
                    delta = event.get("delta") or ""
                    if not delta:
                        continue
                    if hub is not None and not started:
                        hub.publish_orchestrator_message_started(
                            session_id=session.session_id,
                            assistant_message_id=saved.message_id,
                            response_id=response_id,
                        )
                        started = True
                    output_text = _merge_stream_content(output_text, delta)
                    self._repository.save(
                        saved.model_copy(
                            update={
                                "blocks": [OrchestratorMessageBlock(type="markdown", text=output_text)],
                                "state": OrchestratorMessageState.STREAMING,
                            }
                        )
                    )
                    if hub is not None:
                        hub.publish_orchestrator_message_delta(
                            session_id=session.session_id,
                            assistant_message_id=saved.message_id,
                            delta=delta,
                        )
                    continue

                if event_type == "response_completed":
                    response_id = event.get("response_id") or response_id
                    completed_output_text = event.get("output_text") or ""
                    if completed_output_text and completed_output_text not in output_text:
                        output_text = completed_output_text
                    continue

                if event_type == "response_failed":
                    detail = event.get("error") or "streaming failed"
                    failed = saved.model_copy(update={"state": OrchestratorMessageState.FAILED})
                    self._repository.save(failed)
                    if hub is not None:
                        hub.publish_orchestrator_message_failed(
                            session_id=session.session_id,
                            assistant_message_id=saved.message_id,
                            error=detail,
                        )
                    raise ValueError(detail)
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            if exception.response is not None:
                try:
                    detail = exception.response.text or detail
                except Exception:  # noqa: BLE001
                    pass
            failed = saved.model_copy(update={"state": OrchestratorMessageState.FAILED})
            self._repository.save(failed)
            if hub is not None:
                hub.publish_orchestrator_message_failed(
                    session_id=session.session_id,
                    assistant_message_id=saved.message_id,
                    error=detail,
                )
            raise ValueError(detail) from exception
        except Exception:
            raise

        completed = saved.model_copy(
            update={
                "blocks": [OrchestratorMessageBlock(type="markdown", text=output_text)],
                "state": OrchestratorMessageState.COMPLETED,
            }
        )
        self._repository.save(completed)
        if hub is not None and not started:
            hub.publish_orchestrator_message_started(
                session_id=session.session_id,
                assistant_message_id=saved.message_id,
                response_id=response_id,
            )
        if hub is not None:
            hub.publish_orchestrator_message_completed(
                session_id=session.session_id,
                assistant_message_id=saved.message_id,
                response_id=response_id,
                content=output_text,
                blocks=[block.model_dump(mode="json") for block in completed.blocks],
            )
        return OrchestratorChatSubmissionResult(
            session_id=session.session_id,
            assistant_message_id=saved.message_id,
        )

    def _build_context_messages(self, session_id: str, user_message: str) -> list[ChatMessage]:
        history = self._repository.list_messages(session_id)
        messages: list[ChatMessage] = []
        for item in history[-12:]:
            text = "\n\n".join(block.text for block in item.blocks if block.type == "markdown" and block.text)
            if not text:
                continue
            role = "assistant" if item.role == OrchestratorMessageRole.SYSTEM else item.role.value
            if role not in {"user", "assistant"}:
                continue
            messages.append(ChatMessage(role=role, content=text))

        if not messages or messages[-1].role != "user" or messages[-1].content != user_message:
            messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def _append_message(
        self,
        message: OrchestratorMessage,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorMessage:
        saved = self._repository.append(message)
        if hub is not None:
            hub.publish_orchestrator_message_appended(saved.model_dump(mode="json"))
        return saved


def _merge_stream_content(current_content: str, delta: str) -> str:
    if not current_content:
        return delta
    if not delta:
        return current_content
    if delta.startswith(current_content):
        return delta
    if current_content.startswith(delta) or delta in current_content:
        return current_content
    max_overlap = min(len(current_content), len(delta))
    for overlap in range(max_overlap, 0, -1):
        if current_content[-overlap:] == delta[:overlap]:
            return f"{current_content}{delta[overlap:]}"
    return f"{current_content}{delta}"


def build_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
