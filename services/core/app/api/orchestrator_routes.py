from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_chat_gateway, get_orchestrator_conversation_service, get_orchestrator_service
from app.domain.models import (
    OrchestratorCoordinationMode,
    OrchestratorDelegateCompletionPayload,
    OrchestratorDelegateStopPayload,
    OrchestratorSchedulerSnapshot,
    OrchestratorSession,
    OrchestratorSessionStatus,
    OrchestratorTask,
    OrchestratorTaskStatus,
)
from app.llm.gateway import ChatGateway
from app.orchestrator.conversation_models import (
    OrchestratorChatSubmissionResult,
    OrchestratorMessage,
    OrchestratorMessageBlock,
)
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


class OrchestratorConsoleCommandRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    project_path: str | None = None


class OrchestratorConsoleCommandResponse(BaseModel):
    session: OrchestratorSession
    assistant_message_id: str
    created_session: bool


class OrchestratorMessagesDeleteResponse(BaseModel):
    session_id: str
    deleted_count: int


class OrchestratorSessionDeleteResponse(BaseModel):
    session_id: str
    deleted: bool
    cleared_messages: int = 0


def build_orchestrator_router() -> APIRouter:
    router = APIRouter()
    max_suggested_commands = 3

    def _hub(request: Request):
        return getattr(request.app.state, "realtime_hub", None)

    def _raise_client_error(error: ValueError) -> None:
        detail = str(error)
        status_code = 409
        if any(token in detail for token in ["not found"]):
            status_code = 404
        elif any(token in detail for token in ["required", "must", "not ready", "no imported", "project_path", "unsupported"]):
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail) from error

    def _is_approval_message(message: str) -> bool:
        return any(token in message for token in ["批准计划", "审批通过", "开始执行", "开工", "批准并开工"])

    def _is_reject_message(message: str) -> bool:
        return any(token in message for token in ["拒绝计划", "否决计划", "重新规划", "驳回计划"])

    def _is_cancel_message(message: str) -> bool:
        return any(token in message for token in ["退出主控", "取消主控", "结束主控", "取消会话"])

    def _is_resume_message(message: str) -> bool:
        normalized = _normalize_lightweight_chat_command(message)
        return normalized in {
            "恢复主控",
            "继续推进",
            "重派",
            "恢复会话",
            "重跑验收",
        }

    def _is_generate_plan_message(message: str) -> bool:
        return any(token in message for token in ["生成计划", "修改计划", "重新计划", "给我一个计划", "制定计划"])

    def _normalize_lightweight_chat_command(message: str) -> str:
        normalized = "".join(message.strip().split())
        while normalized and normalized[-1] in {"。", "！", "!", "，", ",", "；", ";"}:
            normalized = normalized[:-1]
        return normalized

    def _is_continue_alias(message: str) -> bool:
        normalized = _normalize_lightweight_chat_command(message)
        return normalized in {
            "继续",
            "继续推进",
            "继续推进下去",
            "推进一下",
            "先跑起来",
            "继续跑",
            "继续干",
        }

    def _map_numeric_choice_to_command(session: OrchestratorSession, choice: str) -> str | None:
        if choice not in {"1", "2", "3"}:
            return None

        if session.status == OrchestratorSessionStatus.PENDING_PLAN_APPROVAL:
            if choice == "1":
                return "批准计划"
            if choice in {"2", "3"}:
                return "拒绝计划"

        if session.status in {OrchestratorSessionStatus.FAILED, OrchestratorSessionStatus.CANCELLED}:
            return "恢复主控"

        waiting_reason = (session.coordination.waiting_reason if session.coordination else "") or ""
        if "高风险" in waiting_reason and choice == "1":
            return "批准高风险任务并继续"

        return None

    def _resolve_continue_alias_to_next_command(session: OrchestratorSession, message: str) -> str:
        normalized = message.strip()
        if not normalized or not _is_continue_alias(normalized):
            return normalized
        _, suggestion_items = _resolve_next_action_hint(session)
        for item in suggestion_items:
            command = item.get("command") if isinstance(item, dict) else None
            if not isinstance(command, str):
                continue
            candidate = command.strip()
            if not candidate:
                continue
            if _normalize_lightweight_chat_command(candidate) == _normalize_lightweight_chat_command(normalized):
                continue
            return candidate
        return normalized

    def _build_mapped_command_notice(*, original_message: str, mapped_message: str) -> str | None:
        original = original_message.strip()
        mapped = mapped_message.strip()
        if not original or not mapped or original == mapped:
            return None
        return f"已按当前主控状态执行为：{mapped}"

    def _handle_command_message(
        *,
        session_id: str,
        message: str,
        request: Request,
        orchestrator_service: OrchestratorService,
        conversation_service: OrchestratorConversationService,
        save_user_message: bool,
        directive_fallback_to_chat: bool = False,
    ) -> tuple[OrchestratorSession | None, str | None]:
        normalized = message.strip()
        current_session = orchestrator_service.get_session(session_id)
        mapped_choice_command = _map_numeric_choice_to_command(current_session, normalized)
        if mapped_choice_command is not None:
            normalized = mapped_choice_command
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
            try:
                session = orchestrator_service.apply_directive(session_id, normalized, hub=_hub(request))
            except ValueError as error:
                if directive_fallback_to_chat and str(error) == "unsupported orchestrator directive":
                    return None, None
                raise error
            return session, session.summary or "主控边界已经更新。"
        except ValueError as error:
            raise error

        return None, None

    def _should_trigger_scheduler_after_command(session: OrchestratorSession) -> bool:
        return session.status in {
            OrchestratorSessionStatus.DISPATCHING,
            OrchestratorSessionStatus.RUNNING,
        }

    def _trigger_scheduler_after_command(
        *,
        session: OrchestratorSession,
        request: Request,
        orchestrator_service: OrchestratorService,
    ) -> OrchestratorSession:
        if not _should_trigger_scheduler_after_command(session):
            return session
        orchestrator_service.run_scheduler_tick(hub=_hub(request))
        return orchestrator_service.get_session(session.session_id)

    def _build_chat_assignment_queue_receipt(
        *,
        session: OrchestratorSession,
        directive_message: str,
    ) -> tuple[str | None, OrchestratorMessageBlock | None]:
        if session.plan is None:
            return None, None

        matched_task = None
        for task in session.plan.tasks:
            assignment_source = task.assignment_source.strip() if isinstance(task.assignment_source, str) else None
            if not assignment_source:
                artifacts = task.artifacts or {}
                fallback_source = artifacts.get("source")
                if isinstance(fallback_source, str) and fallback_source.strip():
                    assignment_source = fallback_source.strip()
            if assignment_source != "chat_assignment":
                continue
            assignment_directive = task.assignment_directive.strip() if isinstance(task.assignment_directive, str) else None
            if not assignment_directive:
                artifacts = task.artifacts or {}
                fallback_directive = artifacts.get("directive")
                if isinstance(fallback_directive, str) and fallback_directive.strip():
                    assignment_directive = fallback_directive.strip()
            if assignment_directive != directive_message:
                continue
            matched_task = task
            break

        if matched_task is None:
            return None, None

        coordination = session.coordination
        queue_line: str
        if coordination is None:
            queue_line = f"当前排队位次: 未知（任务ID: {matched_task.task_id}）"
        elif coordination.queue_position is not None:
            queue_line = f"当前排队位次: #{coordination.queue_position}（任务ID: {matched_task.task_id}）"
        elif coordination.mode == OrchestratorCoordinationMode.RUNNING and coordination.dispatch_slot is not None:
            queue_line = f"当前排队位次: 已进入执行槽位 #{coordination.dispatch_slot}（任务ID: {matched_task.task_id}）"
        elif coordination.mode == OrchestratorCoordinationMode.READY:
            queue_line = f"当前排队位次: 待派发（任务ID: {matched_task.task_id}）"
        else:
            queue_line = f"当前排队位次: {coordination.mode.value}（任务ID: {matched_task.task_id}）"

        next_action, suggestion_items = _resolve_next_action_hint(session)
        suggested_commands = [
            item["command"]
            for item in suggestion_items
            if isinstance(item, dict) and isinstance(item.get("command"), str)
        ]
        suggested_command = suggested_commands[0] if suggested_commands else "继续推进"
        receipt_text = "\n".join(
            [
                queue_line,
                f"下一动作: {next_action}",
                f"建议指令: {suggested_command}",
            ]
        )
        suggestion_block = OrchestratorMessageBlock(
            type="next_action_card",
            summary="主控下一步建议",
            details={
                "task_id": matched_task.task_id,
                "queue_line": queue_line,
                "next_action": next_action,
                "suggested_command": suggested_command,
                "suggested_commands": suggested_commands,
                "suggestions": suggestion_items,
            },
        )
        return receipt_text, suggestion_block

    def _build_suggestion(
        *,
        command: str,
        priority: str,
        reason: str,
        confidence: float,
    ) -> dict[str, object]:
        normalized_command = command.strip()
        normalized_priority = "recommended" if priority == "recommended" else "alternative"
        normalized_confidence = min(1.0, max(0.0, confidence))
        return {
            "command": normalized_command,
            "priority": normalized_priority,
            "reason": reason.strip(),
            "confidence": normalized_confidence,
        }

    def _normalize_suggestions(suggestions: list[dict[str, object]]) -> list[dict[str, object]]:
        priority_rank = {"recommended": 0, "alternative": 1}
        deduped: dict[str, dict[str, object]] = {}
        for item in suggestions:
            command = item.get("command")
            if not isinstance(command, str) or not command.strip():
                continue
            normalized_command = command.strip()
            priority = item.get("priority")
            normalized_priority = "recommended" if priority == "recommended" else "alternative"
            confidence_raw = item.get("confidence")
            confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.5
            confidence = min(1.0, max(0.0, confidence))
            reason = item.get("reason")
            normalized_reason = reason.strip() if isinstance(reason, str) else ""
            normalized = {
                "command": normalized_command,
                "priority": normalized_priority,
                "reason": normalized_reason,
                "confidence": confidence,
            }

            existing = deduped.get(normalized_command)
            if existing is None:
                deduped[normalized_command] = normalized
                continue

            existing_rank = priority_rank.get(str(existing.get("priority")), 1)
            new_rank = priority_rank.get(normalized_priority, 1)
            existing_confidence = float(existing.get("confidence", 0.5))
            if new_rank < existing_rank or (new_rank == existing_rank and confidence > existing_confidence):
                deduped[normalized_command] = normalized

        ordered = sorted(
            deduped.values(),
            key=lambda item: (
                priority_rank.get(str(item.get("priority")), 1),
                -float(item.get("confidence", 0.5)),
                str(item.get("command", "")),
            ),
        )
        return ordered[:max_suggested_commands]

    def _resolve_engineer_followup_command(task: OrchestratorTask) -> str | None:
        engineer_label = task.engineer_label.strip() if isinstance(task.engineer_label, str) else ""
        if engineer_label:
            return f"追问{engineer_label}卡点并给建议"

        engineer_id = task.engineer_id if isinstance(task.engineer_id, int) else None
        if engineer_id is None:
            artifacts = task.artifacts or {}
            fallback_engineer_id = artifacts.get("engineer_id")
            if isinstance(fallback_engineer_id, int):
                engineer_id = fallback_engineer_id
        if isinstance(engineer_id, int) and engineer_id > 0:
            return f"追问工程师{engineer_id}号(codex)卡点并给建议"
        return None

    def _resolve_stall_level(task: OrchestratorTask) -> str | None:
        stall_level = task.stall_level.strip() if isinstance(task.stall_level, str) else ""
        if stall_level:
            return stall_level

        if task.stall_followup is not None:
            level = task.stall_followup.level.strip() if isinstance(task.stall_followup.level, str) else ""
            if level:
                return level

        artifacts = task.artifacts or {}
        followup = artifacts.get("stall_followup")
        if isinstance(followup, dict):
            level = followup.get("level")
            if isinstance(level, str) and level.strip():
                return level.strip()
        fallback_level = artifacts.get("stall_level")
        if isinstance(fallback_level, str) and fallback_level.strip():
            return fallback_level.strip()
        return None

    def _resolve_next_action_hint(session: OrchestratorSession) -> tuple[str, list[dict[str, object]]]:
        coordination = session.coordination
        waiting_reason = (coordination.waiting_reason if coordination is not None else "") or ""

        if session.status == OrchestratorSessionStatus.PENDING_PLAN_APPROVAL:
            return "等待计划审批。", _normalize_suggestions(
                [
                    _build_suggestion(
                        command="批准计划并开工",
                        priority="recommended",
                        reason="当前会话被计划审批门禁阻塞，批准后才会进入调度。",
                        confidence=0.93,
                    ),
                    _build_suggestion(
                        command="先解释一下这份计划为什么这么拆",
                        priority="alternative",
                        reason="先确认拆解逻辑，降低批准后的返工风险。",
                        confidence=0.78,
                    ),
                ]
            )
        if "高风险" in waiting_reason:
            return "等待高风险任务二次审批。", _normalize_suggestions(
                [
                    _build_suggestion(
                        command="批准高风险任务并继续",
                        priority="recommended",
                        reason="当前任务因高风险策略暂停，需显式放行才能继续推进。",
                        confidence=0.9,
                    ),
                    _build_suggestion(
                        command="先解释当前推进到哪一步",
                        priority="alternative",
                        reason="先确认风险上下文，再决定是否放行。",
                        confidence=0.76,
                    ),
                ]
            )
        if session.status in {OrchestratorSessionStatus.FAILED, OrchestratorSessionStatus.CANCELLED}:
            return "当前会话已中断，需要恢复。", _normalize_suggestions(
                [
                    _build_suggestion(
                        command="恢复主控",
                        priority="recommended",
                        reason="会话处于终态，需要先恢复到可调度状态。",
                        confidence=0.92,
                    ),
                    _build_suggestion(
                        command="解释一下这次主控为什么中断，以及下一步建议",
                        priority="alternative",
                        reason="先定位中断原因，可以避免重复失败。",
                        confidence=0.8,
                    ),
                ]
            )
        if coordination is not None and coordination.mode in {
            OrchestratorCoordinationMode.QUEUED,
            OrchestratorCoordinationMode.PREEMPTED,
        }:
            return "等待并行名额释放。", _normalize_suggestions(
                [
                    _build_suggestion(
                        command="继续推进",
                        priority="recommended",
                        reason="保持调度心跳，名额释放后可立即继续执行。",
                        confidence=0.88,
                    ),
                    _build_suggestion(
                        command="先解释当前推进到哪一步",
                        priority="alternative",
                        reason="可先获得当前队列状态和预计执行路径。",
                        confidence=0.74,
                    ),
                ]
            )

        if session.plan is not None:
            running_task = next((task for task in session.plan.tasks if task.status == OrchestratorTaskStatus.RUNNING), None)
            if running_task is not None:
                followup_command = _resolve_engineer_followup_command(running_task)
                stall_level = _resolve_stall_level(running_task)
                if followup_command is not None and stall_level in {"soft_ping", "hard_intervention", "manual_followup"}:
                    return (
                        f"任务「{running_task.title}」疑似卡点，建议先追问执行工程师。",
                        _normalize_suggestions(
                            [
                                _build_suggestion(
                                    command=followup_command,
                                    priority="recommended",
                                    reason="主控已检测到该任务长时间无回执，先同步卡点再推进最稳妥。",
                                    confidence=0.91,
                                ),
                                _build_suggestion(
                                    command=f"解释一下任务「{running_task.title}」现在推进到哪一步",
                                    priority="alternative",
                                    reason="用于补充上下文，确认卡点前后的进展轨迹。",
                                    confidence=0.8,
                                ),
                            ]
                        ),
                    )
                return (
                    f"任务「{running_task.title}」正在运行。",
                    _normalize_suggestions(
                        [
                            _build_suggestion(
                                command=f"解释一下任务「{running_task.title}」现在推进到哪一步",
                                priority="recommended",
                                reason="当前任务正在执行，先获取实时进度最有效。",
                                confidence=0.86,
                            ),
                            _build_suggestion(
                                command=followup_command or "追问当前执行工程师卡点并给建议",
                                priority="alternative",
                                reason="如果长时间无回执，可直接触发主控追问与介入建议。",
                                confidence=0.79,
                            ),
                            _build_suggestion(
                                command="请检查当前进度并总结",
                                priority="alternative",
                                reason="适合在阶段切换前做一次状态收敛。",
                                confidence=0.77,
                            ),
                        ]
                    ),
                )

            pending_task = next(
                (
                    task
                    for task in session.plan.tasks
                    if task.status in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}
                ),
                None,
            )
            if pending_task is not None:
                return (
                    f"等待推进任务「{pending_task.title}」。",
                    _normalize_suggestions(
                        [
                            _build_suggestion(
                                command=f"继续推进任务「{pending_task.title}」，并告诉我你准备怎么做",
                                priority="recommended",
                                reason="存在可执行任务，直接推进能缩短等待时间。",
                                confidence=0.87,
                            ),
                            _build_suggestion(
                                command="先解释当前推进到哪一步",
                                priority="alternative",
                                reason="先同步上下文，避免推进方向偏离。",
                                confidence=0.75,
                            ),
                        ]
                    ),
                )

        return "等待主控下一步指令。", _normalize_suggestions(
            [
                _build_suggestion(
                    command="继续推进",
                    priority="recommended",
                    reason="默认保持任务推进节奏。",
                    confidence=0.82,
                ),
                _build_suggestion(
                    command="先解释当前推进到哪一步",
                    priority="alternative",
                    reason="先了解现状，再决定下一步动作。",
                    confidence=0.72,
                ),
            ]
        )

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
        status: list[OrchestratorSessionStatus] | None = Query(default=None),
        project: str | None = Query(default=None),
        from_time: datetime | None = Query(default=None, alias="from"),
        to_time: datetime | None = Query(default=None, alias="to"),
        keyword: str | None = Query(default=None),
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> list[OrchestratorSession]:
        return service.list_sessions(
            statuses=status,
            project=project,
            from_time=from_time,
            to_time=to_time,
            keyword=keyword,
        )

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

    @router.delete("/orchestrator/sessions/{session_id}", response_model=OrchestratorSessionDeleteResponse)
    def delete_session(
        session_id: str,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSessionDeleteResponse:
        try:
            cleared_messages = service.delete_session(session_id, hub=_hub(request))
            return OrchestratorSessionDeleteResponse(
                session_id=session_id,
                deleted=True,
                cleared_messages=cleared_messages,
            )
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

    @router.delete("/orchestrator/sessions/{session_id}/messages", response_model=OrchestratorMessagesDeleteResponse)
    def clear_messages(
        session_id: str,
        service: OrchestratorService = Depends(get_orchestrator_service),
        conversation_service: OrchestratorConversationService = Depends(get_orchestrator_conversation_service),
    ) -> OrchestratorMessagesDeleteResponse:
        try:
            service.get_session(session_id)
            deleted_count = conversation_service.clear_messages(session_id)
            return OrchestratorMessagesDeleteResponse(session_id=session_id, deleted_count=deleted_count)
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
            mapped_message = _resolve_continue_alias_to_next_command(session, user_message)
            mapped_notice = _build_mapped_command_notice(
                original_message=user_message,
                mapped_message=mapped_message,
            )
            conversation_service.append_user_message(session_id, user_message, hub=_hub(request))

            handled_session, reply = _handle_command_message(
                session_id=session_id,
                message=mapped_message,
                request=request,
                orchestrator_service=service,
                conversation_service=conversation_service,
                save_user_message=False,
                directive_fallback_to_chat=True,
            )
            if handled_session is not None and reply is not None:
                latest_session = _trigger_scheduler_after_command(
                    session=handled_session,
                    request=request,
                    orchestrator_service=service,
                )
                queue_receipt, suggestion_block = _build_chat_assignment_queue_receipt(
                    session=latest_session,
                    directive_message=user_message,
                )
                final_reply = reply if not queue_receipt else f"{reply}\n\n{queue_receipt}"
                if mapped_notice is not None:
                    final_reply = f"{mapped_notice}\n\n{final_reply}"
                assistant_message = conversation_service.append_assistant_message(
                    latest_session,
                    final_reply,
                    blocks=[suggestion_block] if suggestion_block is not None else None,
                    hub=_hub(request),
                )
                return OrchestratorChatSubmissionResult(
                    session_id=latest_session.session_id,
                    assistant_message_id=assistant_message.message_id,
                )

            if mapped_notice is not None:
                conversation_service.append_system_event(
                    session,
                    summary=mapped_notice,
                    blocks=[
                        OrchestratorMessageBlock(
                            type="directive_card",
                            summary=mapped_notice,
                            details={
                                "source": "continue_alias_mapping",
                                "original_message": user_message,
                                "mapped_message": mapped_message,
                            },
                        )
                    ],
                    hub=_hub(request),
                )
            return conversation_service.stream_assistant_reply(
                session,
                mapped_message,
                gateway=gateway,
                hub=_hub(request),
            )
        except ValueError as error:
            _raise_client_error(error)

    @router.post("/orchestrator/console/command", response_model=OrchestratorConsoleCommandResponse)
    def run_orchestrator_console_command(
        request_body: OrchestratorConsoleCommandRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        service: OrchestratorService = Depends(get_orchestrator_service),
        conversation_service: OrchestratorConversationService = Depends(get_orchestrator_conversation_service),
    ) -> OrchestratorConsoleCommandResponse:
        try:
            user_message = request_body.message.strip()
            if not user_message:
                raise ValueError("message is required")

            created_session = False
            target_session: OrchestratorSession
            if request_body.session_id is not None and request_body.session_id.strip():
                target_session = service.get_session(request_body.session_id.strip())
            else:
                project_path = request_body.project_path.strip() if isinstance(request_body.project_path, str) else ""
                if not project_path:
                    raise ValueError("project_path is required when session_id is empty")
                target_session = service.create_session(user_message, project_path, hub=_hub(request))
                target_session = service.generate_plan(target_session.session_id, hub=_hub(request))
                target_session = service.approve_plan(target_session.session_id, hub=_hub(request))
                created_session = True

            session_id = target_session.session_id
            mapped_message = _resolve_continue_alias_to_next_command(target_session, user_message)
            mapped_notice = _build_mapped_command_notice(
                original_message=user_message,
                mapped_message=mapped_message,
            )
            conversation_service.append_user_message(session_id, user_message, hub=_hub(request))

            handled_session, reply = _handle_command_message(
                session_id=session_id,
                message=mapped_message,
                request=request,
                orchestrator_service=service,
                conversation_service=conversation_service,
                save_user_message=False,
                directive_fallback_to_chat=True,
            )

            if handled_session is not None and reply is not None:
                latest_session = _trigger_scheduler_after_command(
                    session=handled_session,
                    request=request,
                    orchestrator_service=service,
                )
                queue_receipt, suggestion_block = _build_chat_assignment_queue_receipt(
                    session=latest_session,
                    directive_message=user_message,
                )
                final_reply = reply if not queue_receipt else f"{reply}\n\n{queue_receipt}"
                if mapped_notice is not None:
                    final_reply = f"{mapped_notice}\n\n{final_reply}"
                assistant_message = conversation_service.append_assistant_message(
                    latest_session,
                    final_reply,
                    blocks=[suggestion_block] if suggestion_block is not None else None,
                    hub=_hub(request),
                )
                return OrchestratorConsoleCommandResponse(
                    session=latest_session,
                    assistant_message_id=assistant_message.message_id,
                    created_session=created_session,
                )

            if mapped_notice is not None:
                conversation_service.append_system_event(
                    target_session,
                    summary=mapped_notice,
                    blocks=[
                        OrchestratorMessageBlock(
                            type="directive_card",
                            summary=mapped_notice,
                            details={
                                "source": "continue_alias_mapping",
                                "original_message": user_message,
                                "mapped_message": mapped_message,
                            },
                        )
                    ],
                    hub=_hub(request),
                )

            streamed = conversation_service.stream_assistant_reply(
                target_session,
                mapped_message,
                gateway=gateway,
                hub=_hub(request),
            )
            latest_session = service.get_session(session_id)
            return OrchestratorConsoleCommandResponse(
                session=latest_session,
                assistant_message_id=streamed.assistant_message_id,
                created_session=created_session,
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

    @router.post("/orchestrator/delegates/stop", response_model=OrchestratorSession)
    def stop_delegate(
        payload: OrchestratorDelegateStopPayload,
        request: Request,
        service: OrchestratorService = Depends(get_orchestrator_service),
    ) -> OrchestratorSession:
        try:
            return service.stop_delegate(payload, hub=_hub(request))
        except ValueError as error:
            _raise_client_error(error)

    return router
