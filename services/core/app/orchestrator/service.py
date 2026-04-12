from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Callable
from uuid import uuid4

from app.capabilities.models import CapabilityContext, CapabilityDispatchRequest, CapabilityName, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.domain.models import (
    DelegateCommandResult,
    FocusMode,
    OrchestratorCoordinationMode,
    OrchestratorDelegateCompletionPayload,
    OrchestratorDelegateStopPayload,
    OrchestratorDelegateRun,
    OrchestratorDelegateResult,
    OrchestratorFailureCategory,
    OrchestratorPlan,
    OrchestratorSchedulerSnapshot,
    OrchestratorSession,
    OrchestratorSessionCoordination,
    OrchestratorSessionStatus,
    OrchestratorTask,
    OrchestratorTaskKind,
    OrchestratorTaskStallFollowup,
    OrchestratorTaskStatus,
    OrchestratorVerification,
    OrchestratorVerificationRollup,
    WakeMode,
)
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.delegate_contract import build_delegate_prompt, build_delegate_request
from app.orchestrator.planner import OrchestratorPlanner
from app.orchestrator.project_context import ProjectContextBuilder
from app.orchestrator.repository import OrchestratorSessionRepository
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config

VerificationRunner = Callable[[str, list[str]], OrchestratorVerification]


class OrchestratorService:
    _stuck_verifying_timeout = timedelta(minutes=15)
    _default_delegate_soft_ping_timeout = timedelta(hours=2)
    _default_delegate_no_receipt_timeout = timedelta(hours=6)
    _default_delegate_stall_followup_interval = timedelta(minutes=30)

    def __init__(
        self,
        repository: OrchestratorSessionRepository,
        state_store: StateStore,
        *,
        project_context_builder: ProjectContextBuilder | None = None,
        planner: OrchestratorPlanner | None = None,
        verification_runner: VerificationRunner | None = None,
        max_parallel_sessions: int = 2,
        max_parallel_tasks_per_session: int = 2,
        delegate_soft_ping_timeout: timedelta | None = None,
        delegate_no_receipt_timeout: timedelta | None = None,
        delegate_stall_followup_interval: timedelta | None = None,
        conversation_service: OrchestratorConversationService | None = None,
    ) -> None:
        self._repository = repository
        self._state_store = state_store
        self._project_context_builder = project_context_builder or ProjectContextBuilder()
        self._planner = planner or OrchestratorPlanner()
        self._verification_runner = verification_runner or self._run_verification_commands
        self._max_parallel_sessions = max(1, max_parallel_sessions)
        self._max_parallel_tasks_per_session = max(1, max_parallel_tasks_per_session)
        self._delegate_soft_ping_timeout = (
            self._default_delegate_soft_ping_timeout
            if delegate_soft_ping_timeout is None
            else max(timedelta(minutes=1), delegate_soft_ping_timeout)
        )
        self._delegate_no_receipt_timeout = (
            self._default_delegate_no_receipt_timeout
            if delegate_no_receipt_timeout is None
            else max(self._delegate_soft_ping_timeout, delegate_no_receipt_timeout)
        )
        self._delegate_stall_followup_interval = (
            self._default_delegate_stall_followup_interval
            if delegate_stall_followup_interval is None
            else max(timedelta(minutes=1), delegate_stall_followup_interval)
        )
        self._conversation_service = conversation_service

    def create_session(self, goal: str, project_path: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("goal is required")

        resolved_project_path = self._validate_project_path(project_path)
        session = OrchestratorSession(
            project_path=resolved_project_path,
            project_name=Path(resolved_project_path).name,
            goal=normalized_goal,
            status=OrchestratorSessionStatus.DRAFT,
            coordination=OrchestratorSessionCoordination(
                mode=OrchestratorCoordinationMode.IDLE,
                waiting_reason="等待生成主控计划。",
            ),
            updated_at=self._now(),
        )
        saved = self._repository.save(session)
        self._sync_state(
            saved,
            current_thought=f"已进入主控模式，准备围绕项目 {saved.project_name} 制定执行计划。",
        )
        if self._conversation_service is not None:
            self._conversation_service.append_session_created(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def list_sessions(
        self,
        *,
        statuses: list[OrchestratorSessionStatus] | None = None,
        project: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        keyword: str | None = None,
    ) -> list[OrchestratorSession]:
        sessions = self._repository.list_sessions()
        recovered: list[OrchestratorSession] = []
        for session in sessions:
            next_session = self._recover_stuck_verifying_session(session)
            next_session = self._recover_stalled_running_tasks(next_session)
            next_session = self._normalize_session_task_runtime_fields(next_session)
            if self._matches_session_filters(
                next_session,
                statuses=statuses,
                project=project,
                from_time=from_time,
                to_time=to_time,
                keyword=keyword,
            ):
                recovered.append(next_session)
        return recovered

    def activate_session(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        thought = (
            f"已切换主控项目到 {session.project_name}，继续跟进当前编排会话。"
            if session.status not in self._terminal_statuses()
            else f"已切换查看主控会话：{session.project_name}。"
        )
        self._sync_state(session, current_thought=thought)
        self._publish_session_updated(session, hub)
        return session

    def apply_directive(
        self,
        session_id: str,
        message: str,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("directive message is required")

        session = self._get_session(session_id)
        updated = (
            self._apply_scope_directive(session, normalized_message)
            or self._apply_acceptance_directive(session, normalized_message)
            or self._apply_secondary_approval_directive(session, normalized_message)
            or self._apply_priority_directive(session, normalized_message)
            or self._apply_engineer_followup_directive(session, normalized_message)
            or self._apply_task_assignment_directive(session, normalized_message)
        )
        if updated is None:
            raise ValueError("unsupported orchestrator directive")

        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=f"已接收主控指令：{normalized_message}")
        if self._conversation_service is not None:
            followup_task = self._find_task_for_followup_directive(saved, normalized_message)
            if followup_task is not None:
                self._conversation_service.append_task_update(
                    saved,
                    followup_task,
                    phase="主控追问卡点",
                    hub=hub,
                )
            self._conversation_service.append_directive_applied(saved, normalized_message, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def generate_plan(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        snapshot = self._project_context_builder.build(session.project_path)
        plan = self._planner.build_plan(session.goal, snapshot)
        updated = session.model_copy(
            update={
                "plan": plan,
                "status": OrchestratorSessionStatus.PENDING_PLAN_APPROVAL,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.IDLE,
                    waiting_reason="计划已生成，等待计划级审批。",
                ),
                "verification": None,
                "summary": None,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="主控计划已生成，等待计划级审批。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_generated(saved, hub=hub)
        self._publish_plan_pending(saved, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def approve_plan(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status != OrchestratorSessionStatus.PENDING_PLAN_APPROVAL:
            raise ValueError("session plan is not awaiting approval")

        updated = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.READY,
                    priority_score=self._priority_score(session),
                    waiting_reason="计划已审批，等待调度器分配并行槽。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="收到计划级审批，开始按依赖关系派发任务。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_approved(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def reject_plan(
        self,
        session_id: str,
        *,
        reason: str | None = None,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        session = self._get_session(session_id)
        updated = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.DRAFT,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.IDLE,
                    waiting_reason=reason or "计划被拒绝，等待重新规划。",
                ),
                "summary": reason or "计划被拒绝，等待重新规划。",
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=saved.summary or "计划被拒绝，等待重新规划。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_rejected(saved, reason=reason, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def dispatch(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status not in {OrchestratorSessionStatus.DISPATCHING, OrchestratorSessionStatus.RUNNING}:
            raise ValueError("session is not dispatchable")
        if self._count_running_tasks(session) >= self._max_parallel_tasks_per_session:
            return session

        next_task = self._find_next_dispatchable_task(session)
        if next_task is None:
            if self._has_running_task(session):
                return session
            raise ValueError("no dispatchable task available")

        if self._count_running_sessions(exclude_session_id=session.session_id) >= self._max_parallel_sessions:
            waiting = self._mark_session_waiting_for_slot(
                session,
                queue_position=1,
                waiting_reason="并行名额已满，当前不会抢占正在运行的 delegate。",
                preempted_by_session_id=None,
            )
            saved = self._repository.save(waiting)
            self._publish_session_updated(saved, hub)
            return saved

        return self._dispatch_task(session, next_task, hub=hub)

    def run_scheduler_tick(self, *, hub: AppRealtimeHub | None = None) -> OrchestratorSchedulerSnapshot:
        sessions: list[OrchestratorSession] = []
        for session in self._repository.list_sessions():
            recovered = self._recover_stuck_verifying_session(session)
            recovered = self._recover_stalled_running_tasks(recovered, hub=hub)
            sessions.append(recovered)
        active_session_id = self._active_session_id()
        running_sessions = [session for session in sessions if self._has_running_task(session)]
        available_session_slots = max(0, self._max_parallel_sessions - len(running_sessions))
        dispatch_candidates = [
            session
            for session in sessions
            if session.status in {OrchestratorSessionStatus.DISPATCHING, OrchestratorSessionStatus.RUNNING}
            and self._available_delegate_capacity(session) > 0
            and self._find_next_dispatchable_task(session) is not None
        ]
        dispatch_candidates.sort(key=self._dispatch_priority_key)

        selected_sessions: list[OrchestratorSession] = []
        queued_sessions: list[OrchestratorSession] = []
        selected_ids: set[str] = set()
        remaining_slots = available_session_slots
        for session in dispatch_candidates:
            if self._has_running_task(session):
                selected_sessions.append(session)
                selected_ids.add(session.session_id)
                continue
            if remaining_slots > 0:
                selected_sessions.append(session)
                selected_ids.add(session.session_id)
                remaining_slots -= 1
                continue
            queued_sessions.append(session)

        saved_by_id: dict[str, OrchestratorSession] = {}
        for slot_index, session in enumerate(running_sessions, start=1):
            running_task_count = self._count_running_tasks(session)
            updated = self._with_coordination(
                session,
                mode=OrchestratorCoordinationMode.RUNNING,
                priority_score=self._priority_score(session),
                dispatch_slot=slot_index,
                queue_position=None,
                waiting_reason=f"已占用并行槽，当前有 {running_task_count} 个 delegate 运行中。",
                preempted_by_session_id=None,
            )
            saved_by_id[updated.session_id] = self._save_if_changed(updated, hub=hub)

        for queue_index, session in enumerate(queued_sessions, start=1):
            if len(running_sessions) >= self._max_parallel_sessions:
                waiting_reason = "并行名额已满，当前不会抢占正在运行的 delegate。"
                preempted_by = None
            elif active_session_id is not None and active_session_id in selected_ids and session.session_id != active_session_id:
                waiting_reason = "等待并行名额释放，当前优先让活动主控项目先执行。"
                preempted_by = active_session_id
            else:
                waiting_reason = "等待并行名额释放。"
                preempted_by = None
            updated = self._mark_session_waiting_for_slot(
                session,
                queue_position=queue_index,
                waiting_reason=waiting_reason,
                preempted_by_session_id=preempted_by,
            )
            saved_by_id[updated.session_id] = self._save_if_changed(updated, hub=hub)

        for session in selected_sessions:
            current = saved_by_id.get(session.session_id, session)
            while self._available_delegate_capacity(current) > 0:
                next_dispatchable = self._find_next_dispatchable_task(current)
                if next_dispatchable is None:
                    break
                before = current.model_dump(mode="json")
                current = self._dispatch_task(current, next_dispatchable, hub=hub)
                if current.model_dump(mode="json") == before:
                    break
            saved_by_id[session.session_id] = current

        return self.get_scheduler_snapshot()

    def get_scheduler_snapshot(self) -> OrchestratorSchedulerSnapshot:
        sessions = self._repository.list_sessions()
        active_session_id = self._active_session_id()
        running_session_ids = [session.session_id for session in sessions if self._has_running_task(session)]
        queued_session_ids = [
            session.session_id
            for session in sessions
            if session.coordination is not None
            and session.coordination.mode in {OrchestratorCoordinationMode.QUEUED, OrchestratorCoordinationMode.PREEMPTED}
        ]
        passed_sessions = sum(1 for session in sessions if session.verification is not None and session.verification.passed)
        failed_sessions = sum(
            1
            for session in sessions
            if session.status == OrchestratorSessionStatus.FAILED
            or (session.verification is not None and not session.verification.passed)
        )
        pending_sessions = max(0, len(sessions) - passed_sessions - failed_sessions)
        return OrchestratorSchedulerSnapshot(
            max_parallel_sessions=self._max_parallel_sessions,
            running_sessions=len(running_session_ids),
            available_slots=max(0, self._max_parallel_sessions - len(running_session_ids)),
            queued_sessions=len(queued_session_ids),
            active_session_id=active_session_id,
            running_session_ids=running_session_ids,
            queued_session_ids=queued_session_ids,
            verification_rollup=OrchestratorVerificationRollup(
                total_sessions=len(sessions),
                passed_sessions=passed_sessions,
                failed_sessions=failed_sessions,
                pending_sessions=pending_sessions,
            ),
            policy_note=(
                f"最多并行 {self._max_parallel_sessions} 个项目会话；"
                "活动主控项目优先获得下一次派发权；"
                "已经运行中的 delegate 不会被硬中断。"
            ),
        )

    def _dispatch_task(
        self,
        session: OrchestratorSession,
        next_task: OrchestratorTask,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        high_risk_reason = self._resolve_high_risk_reason(next_task)
        if (
            next_task.kind == OrchestratorTaskKind.IMPLEMENT
            and high_risk_reason is not None
            and not bool(next_task.artifacts.get("secondary_approval_granted"))
        ):
            return self._mark_task_waiting_secondary_approval(
                session,
                next_task,
                reason=high_risk_reason,
                hub=hub,
            )

        delegate_run_id = uuid4().hex
        engineer_id = self._next_engineer_id(session)
        assigned_at = self._now()
        engineer_label = f"工程师{engineer_id}号(codex)"
        delegate_request = build_delegate_request(goal=session.goal, project_path=session.project_path, task=next_task)
        delegate_prompt = build_delegate_prompt(delegate_request)
        updated_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            if task.task_id == next_task.task_id:
                updated_tasks.append(
                    task.model_copy(
                        update={
                            "status": OrchestratorTaskStatus.RUNNING,
                            "delegate_run_id": delegate_run_id,
                            "engineer_id": engineer_id,
                            "engineer_label": engineer_label,
                            "assigned_at": assigned_at,
                            "stall_level": None,
                            "stall_followup": None,
                            "last_stall_followup_at": None,
                            "last_intervened_at": None,
                            "intervention_suggestions": [],
                            "artifacts": {
                                **task.artifacts,
                                "engineer_id": engineer_id,
                                "engineer_label": engineer_label,
                                "assigned_at": assigned_at.isoformat(),
                                "stalled": False,
                                "stall_level": None,
                                "stalled_at": None,
                                "stall_followup": None,
                                "last_stall_followup_at": None,
                                "last_followup_directive": None,
                                "delegate_request": delegate_request.model_dump(mode="json"),
                                "delegate_prompt": delegate_prompt,
                            },
                            "error": None,
                            "result_summary": f"{engineer_label} 已接单，正在执行。",
                        }
                    )
                )
            else:
                updated_tasks.append(task)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        delegates = [
            *session.delegates,
            OrchestratorDelegateRun(
                task_id=next_task.task_id,
                delegate_run_id=delegate_run_id,
                provider=next_task.delegate_target,
            ),
        ]
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "delegates": delegates,
                "status": OrchestratorSessionStatus.RUNNING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.RUNNING,
                    priority_score=self._priority_score(session),
                    dispatch_slot=1,
                    waiting_reason=f"已派发给 {engineer_label}，等待执行回填。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=f"主控已派发任务给 {engineer_label}：{next_task.title}")
        dispatched_task = self._get_task(saved, next_task.task_id)
        if self._conversation_service is not None:
            self._conversation_service.append_task_update(
                saved,
                dispatched_task,
                phase=f"任务已派发（{engineer_label}）",
                hub=hub,
            )
        self._publish_task_updated(saved, dispatched_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def get_session(self, session_id: str) -> OrchestratorSession:
        return self._get_session(session_id)

    def list_tasks(self, session_id: str) -> list[OrchestratorTask]:
        session = self._get_session(session_id)
        return [] if session.plan is None else [task.model_copy(deep=True) for task in session.plan.tasks]

    def delete_session(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> int:
        session = self._get_session(session_id)
        if session.status in {
            OrchestratorSessionStatus.DISPATCHING,
            OrchestratorSessionStatus.RUNNING,
            OrchestratorSessionStatus.VERIFYING,
        } or self._has_running_task(session):
            raise ValueError("session is active; cancel session before deleting history")

        deleted = self._repository.delete(session_id)
        if not deleted:
            raise ValueError("orchestrator session not found")

        removed_messages = (
            self._conversation_service.clear_messages(session_id)
            if self._conversation_service is not None
            else 0
        )
        if self._is_active_session(session_id):
            self._clear_state(current_thought="主控历史会话已删除。")
            if hub is not None:
                hub.publish_runtime()
        return removed_messages

    def cancel(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        updated_tasks: list[OrchestratorTask] = []
        if session.plan is not None:
            for task in session.plan.tasks:
                if task.status in {OrchestratorTaskStatus.SUCCEEDED, OrchestratorTaskStatus.FAILED, OrchestratorTaskStatus.CANCELLED}:
                    updated_tasks.append(task)
                else:
                    updated_tasks.append(task.model_copy(update={"status": OrchestratorTaskStatus.CANCELLED}))
        updated_plan = None if session.plan is None else session.plan.model_copy(update={"tasks": updated_tasks})
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "status": OrchestratorSessionStatus.CANCELLED,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.CANCELLED,
                    waiting_reason="主控会话已取消。",
                    failure_category=None,
                ),
                "summary": session.summary or "主控会话已取消。",
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._clear_state(current_thought="已退出主控模式。")
        if self._conversation_service is not None:
            self._conversation_service.append_session_cancelled(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def resume_session(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status not in {OrchestratorSessionStatus.FAILED, OrchestratorSessionStatus.CANCELLED}:
            raise ValueError("session is not resumable")

        resumed_plan = self._resume_plan(session)
        if resumed_plan is None:
            raise ValueError("session has no resumable tasks")

        summary = "会话已恢复到主控调度队列。"
        updated = session.model_copy(
            update={
                "plan": resumed_plan,
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.READY,
                    priority_score=self._priority_score(session),
                    waiting_reason=summary,
                    failure_category=None,
                ),
                "verification": None,
                "summary": summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=summary)
        if self._conversation_service is not None:
            self._conversation_service.append_system_event(
                saved,
                summary=summary,
                blocks=[self._conversation_service.build_session_status_block(saved)],
                hub=hub,
            )
        self._publish_session_updated(saved, hub)
        return saved

    def complete_delegate(
        self,
        payload: OrchestratorDelegateCompletionPayload,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        session = self._get_session(payload.session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")

        task = self._get_task(session, payload.task_id)
        if task.delegate_run_id != payload.delegate_run_id:
            raise ValueError("delegate run id mismatch")

        normalized_changed_files = self._normalize_changed_files(session.project_path, payload.result)
        scope_error = self._validate_changed_files(task, normalized_changed_files)
        changed_file_evidence_error = (
            self._validate_expected_file_change_evidence(task, normalized_changed_files)
            if payload.result.status == "succeeded"
            else None
        )
        final_error = scope_error or changed_file_evidence_error or payload.result.error
        succeeded = payload.result.status == "succeeded" and final_error is None

        updated_tasks: list[OrchestratorTask] = []
        updated_task: OrchestratorTask | None = None
        for candidate in session.plan.tasks:
            if candidate.task_id == task.task_id:
                updated_task = candidate.model_copy(
                    update={
                        "status": OrchestratorTaskStatus.SUCCEEDED if succeeded else OrchestratorTaskStatus.FAILED,
                        "result_summary": payload.result.summary,
                        "stall_level": None if succeeded else candidate.stall_level,
                        "stall_followup": None if succeeded else candidate.stall_followup,
                        "last_stall_followup_at": None if succeeded else candidate.last_stall_followup_at,
                        "intervention_suggestions": [] if succeeded else candidate.intervention_suggestions,
                        "artifacts": {
                            **candidate.artifacts,
                            "delegate_result": payload.result.model_dump(mode="json"),
                            "changed_files": normalized_changed_files,
                        },
                        "error": final_error,
                    }
                )
                updated_tasks.append(updated_task)
            else:
                updated_tasks.append(candidate)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        updated_delegates = self._complete_delegate_record(session, task.task_id, payload.delegate_run_id, succeeded)
        updated_summary = session.summary
        if not succeeded:
            updated_summary = final_error or payload.result.summary or f"任务失败：{task.title}"

        next_running_count = sum(1 for item in updated_tasks if item.status == OrchestratorTaskStatus.RUNNING)
        if succeeded:
            if next_running_count > 0:
                updated_status = OrchestratorSessionStatus.RUNNING
                coordination_mode = OrchestratorCoordinationMode.RUNNING
                waiting_reason = f"当前仍有 {next_running_count} 个任务执行中，等待 delegate 回填。"
            else:
                updated_status = OrchestratorSessionStatus.DISPATCHING
                coordination_mode = OrchestratorCoordinationMode.READY
                waiting_reason = "任务已回收，等待下一轮调度。"
            failure_category = None
        else:
            updated_status = OrchestratorSessionStatus.FAILED
            coordination_mode = OrchestratorCoordinationMode.FAILED
            waiting_reason = final_error or payload.result.summary or f"任务失败：{task.title}"
            failure_category = self._classify_failure_category(final_error)

        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "delegates": updated_delegates,
                "status": updated_status,
                "coordination": OrchestratorSessionCoordination(
                    mode=coordination_mode,
                    priority_score=self._priority_score(session),
                    waiting_reason=waiting_reason,
                    failure_category=failure_category,
                ),
                "summary": updated_summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(
                saved,
                current_thought=(
                    f"主控任务失败：{updated_task.title if updated_task is not None else task.title}"
                    if not succeeded
                    else f"任务已回收：{updated_task.title if updated_task is not None else task.title}"
                ),
            )
        if updated_task is not None:
            if self._conversation_service is not None:
                phase = "任务已回收" if succeeded else "任务失败"
                self._conversation_service.append_task_update(saved, updated_task, phase=phase, hub=hub)
            self._publish_task_updated(saved, updated_task, hub)
        self._publish_session_updated(saved, hub)

        if not succeeded:
            return saved

        if updated_task is not None and updated_task.kind == OrchestratorTaskKind.VERIFY:
            saved = self._complete_local_summarize(saved, hub=hub)

        if self._all_tasks_succeeded(saved):
            return self._run_plan_verification(saved, hub=hub)
        return saved

    def stop_delegate(
        self,
        payload: OrchestratorDelegateStopPayload,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        session = self._get_session(payload.session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")

        task = self._get_task(session, payload.task_id)
        if task.delegate_run_id != payload.delegate_run_id:
            raise ValueError("delegate run id mismatch")

        if task.status != OrchestratorTaskStatus.RUNNING:
            if self._is_task_already_stopped_by_orchestrator(task):
                return session
            raise ValueError("delegate task is not running")

        reason = (payload.reason or "").strip()
        summary = reason or f"主控已停止任务：{task.title}"
        error_message = reason or "delegate stopped by orchestrator"

        stopped_result = OrchestratorDelegateResult(
            status="failed",
            summary=summary,
            changed_files=[],
            command_results=[],
            followup_needed=[],
            error=error_message,
        )

        updated_tasks: list[OrchestratorTask] = []
        updated_task: OrchestratorTask | None = None
        for candidate in session.plan.tasks:
            if candidate.task_id == task.task_id:
                updated_task = candidate.model_copy(
                    update={
                        "status": OrchestratorTaskStatus.FAILED,
                        "result_summary": summary,
                        "last_intervened_at": self._now(),
                        "artifacts": {
                            **candidate.artifacts,
                            "delegate_result": stopped_result.model_dump(mode="json"),
                            "changed_files": [],
                            "stopped_by_orchestrator": True,
                            "stop_reason": reason or None,
                            "stopped_at": self._now().isoformat(),
                        },
                        "error": error_message,
                    }
                )
                updated_tasks.append(updated_task)
            else:
                updated_tasks.append(candidate)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        updated_delegates = self._complete_delegate_record(session, task.task_id, payload.delegate_run_id, False)
        waiting_reason = summary
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "delegates": updated_delegates,
                "status": OrchestratorSessionStatus.FAILED,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.FAILED,
                    priority_score=self._priority_score(session),
                    waiting_reason=waiting_reason,
                    failure_category=OrchestratorFailureCategory.DELEGATE_FAILURE,
                ),
                "summary": summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=summary)
        if updated_task is not None:
            if self._conversation_service is not None:
                self._conversation_service.append_task_update(
                    saved,
                    updated_task,
                    phase="任务已停止",
                    hub=hub,
                )
            self._publish_task_updated(saved, updated_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _run_plan_verification(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        commands = self._collect_verification_commands(session)
        verifying = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.VERIFYING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.VERIFYING,
                    priority_score=self._priority_score(session),
                    waiting_reason="正在统一执行计划内验收命令。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        verifying = self._repository.save(verifying)
        if self._is_active_session(verifying.session_id):
            self._sync_state(verifying, current_thought="主控正在统一执行计划内验收命令。")
        self._publish_session_updated(verifying, hub)

        try:
            verification = self._verification_runner(verifying.project_path, commands)
        except Exception as error:  # noqa: BLE001 - guard session state from being stuck in verifying forever.
            message = str(error).strip() or error.__class__.__name__
            verification = OrchestratorVerification(
                commands=commands,
                command_results=[],
                passed=False,
                summary=f"统一验收执行异常：{message}",
            )
        completed = verifying.model_copy(
            update={
                "verification": verification,
                "status": OrchestratorSessionStatus.COMPLETED if verification.passed else OrchestratorSessionStatus.FAILED,
                "coordination": OrchestratorSessionCoordination(
                    mode=(
                        OrchestratorCoordinationMode.COMPLETED
                        if verification.passed
                        else OrchestratorCoordinationMode.FAILED
                    ),
                    priority_score=self._priority_score(verifying),
                    waiting_reason=verification.summary,
                    failure_category=(
                        None
                        if verification.passed
                        else OrchestratorFailureCategory.VERIFICATION_FAILURE
                    ),
                ),
                "summary": verification.summary or verifying.summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(completed)
        if self._is_active_session(saved.session_id):
            self._sync_state(
                saved,
                current_thought=(
                    "主控任务已完成，验证通过。"
                    if verification.passed
                    else "主控任务已回收，但统一验收未通过。"
                ),
            )
        if self._conversation_service is not None:
            self._conversation_service.append_verification_completed(saved, hub=hub)
        self._publish_verification_completed(saved, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _complete_local_summarize(
        self,
        session: OrchestratorSession,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        if session.plan is None:
            return session

        summarize_task = next(
            (
                task
                for task in session.plan.tasks
                if task.kind == OrchestratorTaskKind.SUMMARIZE
                and task.status in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}
            ),
            None,
        )
        if summarize_task is None:
            return session

        succeeded = {task.task_id for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED}
        if not all(dep in succeeded for dep in summarize_task.depends_on):
            return session

        summary_text = self._build_local_summary_text(session)
        updated_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            if task.task_id == summarize_task.task_id:
                updated_tasks.append(
                    task.model_copy(
                        update={
                            "status": OrchestratorTaskStatus.SUCCEEDED,
                            "result_summary": summary_text,
                            "delegate_run_id": None,
                            "error": None,
                            "artifacts": {
                                **task.artifacts,
                                "local_execution": True,
                                "local_summary": summary_text,
                            },
                        }
                    )
                )
            else:
                updated_tasks.append(task)

        updated = session.model_copy(
            update={
                "plan": session.plan.model_copy(update={"tasks": updated_tasks}),
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.READY,
                    priority_score=self._priority_score(session),
                    waiting_reason="本地摘要已完成，准备统一验收。",
                    failure_category=None,
                ),
                "summary": summary_text,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="本地摘要已完成，准备统一验收。")
        updated_task = self._get_task(saved, summarize_task.task_id)
        if self._conversation_service is not None:
            self._conversation_service.append_task_update(saved, updated_task, phase="本地整理完成", hub=hub)
        self._publish_task_updated(saved, updated_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _build_local_summary_text(self, session: OrchestratorSession) -> str:
        if session.plan is None:
            return "本地摘要已完成。"

        changed_files: list[str] = []
        for task in session.plan.tasks:
            raw_changed = task.artifacts.get("changed_files")
            if isinstance(raw_changed, list):
                for item in raw_changed:
                    if isinstance(item, str) and item.strip():
                        changed_files.append(item.strip())
                continue
            delegate_result = task.artifacts.get("delegate_result")
            if isinstance(delegate_result, dict):
                result_files = delegate_result.get("changed_files")
                if isinstance(result_files, list):
                    for item in result_files:
                        if isinstance(item, str) and item.strip():
                            changed_files.append(item.strip())

        unique_files = list(dict.fromkeys(changed_files))
        completed_count = sum(1 for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED)
        return (
            f"本地摘要：任务完成 {completed_count}/{len(session.plan.tasks)}，"
            f"累计改动 {len(unique_files)} 个文件。"
        )

    def _run_verification_commands(self, project_path: str, commands: list[str]) -> OrchestratorVerification:
        if not commands:
            return OrchestratorVerification(commands=[], command_results=[], passed=True, summary="没有额外验收命令，按计划完成。")

        if not has_recent_capability_executor("desktop", max_age_seconds=30):
            return OrchestratorVerification(
                commands=commands,
                command_results=[],
                passed=False,
                summary="未检测到可用的 desktop capability executor，无法执行统一验收。",
            )

        config = get_runtime_config()
        shell_policy = config.get_capability_shell_policy()
        command_results: list[DelegateCommandResult] = []
        all_passed = True

        for command in commands:
            result = dispatch_and_wait(
                CapabilityDispatchRequest(
                    capability=CapabilityName.SHELL_RUN,
                    args={
                        "command": command,
                        "cwd": project_path,
                        "timeout_seconds": 180,
                        "allowed_executables": list(shell_policy["allowed_executables"]),
                        "allowed_git_subcommands": list(shell_policy["allowed_git_subcommands"]),
                    },
                    risk_level=RiskLevel.RESTRICTED,
                    requires_approval=False,
                    context=CapabilityContext(reason="orchestrator verification"),
                ),
                timeout_seconds=185,
                poll_interval_seconds=0.1,
            )
            if result is None:
                command_results.append(
                    DelegateCommandResult(
                        command=command,
                        success=False,
                        exit_code=None,
                        stderr="capability dispatch timeout",
                    )
                )
                all_passed = False
                continue

            output = result.output if isinstance(result.output, dict) else {}
            shell_success = bool(output.get("success", result.ok))
            command_results.append(
                DelegateCommandResult(
                    command=command,
                    success=shell_success,
                    exit_code=output.get("exit_code") if isinstance(output.get("exit_code"), int) else None,
                    stdout=output.get("stdout") if isinstance(output.get("stdout"), str) else None,
                    stderr=(
                        output.get("stderr") if isinstance(output.get("stderr"), str) else result.error_message
                    ),
                    duration_ms=output.get("duration_ms") if isinstance(output.get("duration_ms"), int) else None,
                )
            )
            if not shell_success:
                all_passed = False

        passed_count = sum(1 for item in command_results if item.success)
        return OrchestratorVerification(
            commands=commands,
            command_results=command_results,
            passed=all_passed,
            summary=f"统一验收执行 {len(commands)} 条命令，通过 {passed_count} 条。",
        )

    def _sync_state(self, session: OrchestratorSession, *, current_thought: str) -> None:
        state = self._state_store.get()
        focus_mode = FocusMode.ORCHESTRATOR
        next_state = state.model_copy(
            update={
                "focus_mode": focus_mode,
                "orchestrator_session": session,
                "current_thought": current_thought,
            }
        )
        self._state_store.set(next_state)

    def _clear_state(self, *, current_thought: str) -> None:
        state = self._state_store.get()
        next_focus_mode = FocusMode.AUTONOMY if state.mode == WakeMode.AWAKE else FocusMode.SLEEPING
        next_state = state.model_copy(
            update={
                "focus_mode": next_focus_mode,
                "orchestrator_session": None,
                "current_thought": current_thought,
            }
        )
        self._state_store.set(next_state)

    def _find_next_dispatchable_task(self, session: OrchestratorSession) -> OrchestratorTask | None:
        if session.plan is None:
            return None
        succeeded = {task.task_id for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED}
        for task in session.plan.tasks:
            if task.status not in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}:
                continue
            if all(dep in succeeded for dep in task.depends_on):
                return task
        return None

    def _resume_plan(self, session: OrchestratorSession) -> OrchestratorPlan | None:
        if session.plan is None:
            return None

        should_reset_verify_stage = (
            (session.verification is not None and not session.verification.passed)
            or (
                session.status == OrchestratorSessionStatus.FAILED
                and session.coordination is not None
                and session.coordination.failure_category == OrchestratorFailureCategory.VERIFICATION_FAILURE
            )
            or (
                session.status == OrchestratorSessionStatus.FAILED
                and session.verification is None
                and self._all_tasks_succeeded(session)
            )
        )
        updated_tasks: list[OrchestratorTask] = []
        reset_count = 0

        for task in session.plan.tasks:
            should_reset = False
            if should_reset_verify_stage:
                should_reset = task.kind in {OrchestratorTaskKind.VERIFY, OrchestratorTaskKind.SUMMARIZE}
            else:
                should_reset = task.status != OrchestratorTaskStatus.SUCCEEDED

            if should_reset:
                updated_tasks.append(self._reset_task_for_resume(task))
                reset_count += 1
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if reset_count == 0:
            return None
        return session.plan.model_copy(update={"tasks": updated_tasks})

    def _reset_task_for_resume(self, task: OrchestratorTask) -> OrchestratorTask:
        artifacts = dict(task.artifacts)
        for key in [
            "delegate_request",
            "delegate_prompt",
            "delegate_result",
            "changed_files",
            "stalled",
            "stall_level",
            "stalled_at",
            "stall_followup",
            "last_stall_followup_at",
            "last_followup_directive",
        ]:
            artifacts.pop(key, None)
        return task.model_copy(
            update={
                "status": OrchestratorTaskStatus.PENDING,
                "result_summary": None,
                "artifacts": artifacts,
                "delegate_run_id": None,
                "engineer_id": None,
                "engineer_label": None,
                "assigned_at": None,
                "stall_level": None,
                "stall_followup": None,
                "last_stall_followup_at": None,
                "last_intervened_at": None,
                "intervention_suggestions": [],
                "error": None,
            }
        )

    def _classify_failure_category(self, error: str | None) -> OrchestratorFailureCategory:
        if error and "outside approved scope" in error:
            return OrchestratorFailureCategory.POLICY_VIOLATION
        if error and "forbidden path" in error:
            return OrchestratorFailureCategory.POLICY_VIOLATION
        return OrchestratorFailureCategory.DELEGATE_FAILURE

    def _has_running_task(self, session: OrchestratorSession) -> bool:
        return self._count_running_tasks(session) > 0

    def _count_running_tasks(self, session: OrchestratorSession) -> int:
        if session.plan is None:
            return 0
        return sum(1 for task in session.plan.tasks if task.status == OrchestratorTaskStatus.RUNNING)

    def _available_delegate_capacity(self, session: OrchestratorSession) -> int:
        if session.plan is None:
            return 0
        return max(0, self._max_parallel_tasks_per_session - self._count_running_tasks(session))

    def _next_engineer_id(self, session: OrchestratorSession) -> int:
        in_use: set[int] = set()
        if session.plan is not None:
            for task in session.plan.tasks:
                if task.status != OrchestratorTaskStatus.RUNNING:
                    continue
                engineer_id = task.engineer_id
                if not isinstance(engineer_id, int) or engineer_id <= 0:
                    engineer_id = task.artifacts.get("engineer_id")
                if isinstance(engineer_id, int) and engineer_id > 0:
                    in_use.add(engineer_id)
        for candidate in range(1, self._max_parallel_tasks_per_session + 1):
            if candidate not in in_use:
                return candidate
        return max(1, len(in_use) + 1)

    def _resolve_engineer_identity(self, task: OrchestratorTask) -> tuple[int, str]:
        engineer_id = task.engineer_id
        if not isinstance(engineer_id, int) or engineer_id <= 0:
            engineer_id = task.artifacts.get("engineer_id")
        if not isinstance(engineer_id, int) or engineer_id <= 0:
            engineer_id = 1
        engineer_label = task.engineer_label
        if not isinstance(engineer_label, str) or not engineer_label.strip():
            engineer_label = task.artifacts.get("engineer_label")
        if not isinstance(engineer_label, str) or not engineer_label.strip():
            engineer_label = f"工程师{engineer_id}号(codex)"
        else:
            engineer_label = engineer_label.strip()
        return engineer_id, engineer_label

    def _build_engineer_followup_command(self, engineer_label: str) -> str:
        return f"追问{engineer_label}卡点并给建议"

    def _count_running_sessions(self, *, exclude_session_id: str | None = None) -> int:
        count = 0
        for session in self._repository.list_sessions():
            if exclude_session_id is not None and session.session_id == exclude_session_id:
                continue
            if self._has_running_task(session):
                count += 1
        return count

    def _priority_score(self, session: OrchestratorSession) -> int:
        score = len(session.plan.tasks) if session.plan is not None else 0
        if self._is_active_session(session.session_id):
            score += 100
        if session.status == OrchestratorSessionStatus.RUNNING:
            score += 20
        if session.plan is not None:
            score += sum(10 for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED)
        score += session.priority_bias
        return score

    def _dispatch_priority_key(self, session: OrchestratorSession) -> tuple[int, float]:
        return (-self._priority_score(session), session.entered_at.timestamp())

    def _mark_session_waiting_for_slot(
        self,
        session: OrchestratorSession,
        *,
        queue_position: int,
        waiting_reason: str,
        preempted_by_session_id: str | None,
    ) -> OrchestratorSession:
        next_task = self._find_next_dispatchable_task(session)
        updated_plan = session.plan
        if session.plan is not None and next_task is not None:
            updated_tasks: list[OrchestratorTask] = []
            for task in session.plan.tasks:
                if task.task_id == next_task.task_id and task.status in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}:
                    updated_tasks.append(task.model_copy(update={"status": OrchestratorTaskStatus.QUEUED}))
                else:
                    updated_tasks.append(task)
            updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})

        mode = (
            OrchestratorCoordinationMode.PREEMPTED
            if preempted_by_session_id is not None
            else OrchestratorCoordinationMode.QUEUED
        )
        return session.model_copy(
            update={
                "plan": updated_plan,
                "coordination": OrchestratorSessionCoordination(
                    mode=mode,
                    priority_score=self._priority_score(session),
                    queue_position=queue_position,
                waiting_reason=waiting_reason,
                failure_category=None,
                preempted_by_session_id=preempted_by_session_id,
            ),
            "updated_at": self._now(),
        }
        )

    def _mark_task_waiting_secondary_approval(
        self,
        session: OrchestratorSession,
        task: OrchestratorTask,
        *,
        reason: str,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        wait_message = f"检测到高风险变更，任务「{task.title}」需二次审批后才能执行。原因：{reason}"
        already_waiting = (
            session.coordination is not None
            and session.coordination.mode == OrchestratorCoordinationMode.QUEUED
            and session.coordination.waiting_reason == wait_message
            and task.status == OrchestratorTaskStatus.QUEUED
            and task.artifacts.get("secondary_approval_required") is True
            and task.artifacts.get("secondary_approval_granted") is not True
        )
        if already_waiting:
            return session

        if session.plan is None:
            return session

        updated_tasks: list[OrchestratorTask] = []
        for current in session.plan.tasks:
            if current.task_id == task.task_id:
                updated_tasks.append(
                    current.model_copy(
                        update={
                            "status": OrchestratorTaskStatus.QUEUED,
                            "artifacts": {
                                **current.artifacts,
                                "secondary_approval_required": True,
                                "secondary_approval_reason": reason,
                                "secondary_approval_granted": False,
                            },
                        }
                    )
                )
            else:
                updated_tasks.append(current)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.QUEUED,
                    priority_score=self._priority_score(session),
                    waiting_reason=wait_message,
                    failure_category=None,
                ),
                "summary": wait_message,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=wait_message)
        updated_task = self._get_task(saved, task.task_id)
        if self._conversation_service is not None:
            self._conversation_service.append_task_update(saved, updated_task, phase="待二次审批", hub=hub)
        self._publish_task_updated(saved, updated_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _resolve_high_risk_reason(self, task: OrchestratorTask) -> str | None:
        if task.kind != OrchestratorTaskKind.IMPLEMENT:
            return None

        normalized_scope = [item.strip().strip("/") for item in task.scope_paths if item.strip()]
        reasons: list[str] = []
        if "." in normalized_scope:
            reasons.append("scope 覆盖项目根目录")
        if len(normalized_scope) >= 4:
            reasons.append("scope 覆盖目录过多")
        top_level_crossing = [item for item in normalized_scope if item in {"apps", "services", "packages"}]
        if len(top_level_crossing) >= 2:
            reasons.append("跨多个顶级模块同时改动")

        dangerous_patterns = [
            r"\brm\s+-rf\b",
            r"\bsudo\b",
            r"git\s+reset\s+--hard",
            r"git\s+checkout\s+--\s",
            r"curl\s+.+\|\s*(?:sh|bash)",
            r"chmod\s+-R",
        ]
        for command in task.acceptance_commands:
            if any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in dangerous_patterns):
                reasons.append(f"验收命令存在高风险动作：{command}")
                break

        if not reasons:
            return None
        return "；".join(list(dict.fromkeys(reasons)))

    def _with_coordination(
        self,
        session: OrchestratorSession,
        *,
        mode: OrchestratorCoordinationMode,
        priority_score: int,
        dispatch_slot: int | None = None,
        queue_position: int | None = None,
        waiting_reason: str | None = None,
        preempted_by_session_id: str | None = None,
    ) -> OrchestratorSession:
        return session.model_copy(
            update={
                "coordination": OrchestratorSessionCoordination(
                    mode=mode,
                    priority_score=priority_score,
                    dispatch_slot=dispatch_slot,
                    queue_position=queue_position,
                    waiting_reason=waiting_reason,
                    failure_category=None,
                    preempted_by_session_id=preempted_by_session_id,
                ),
                "updated_at": self._now(),
            }
        )

    def _save_if_changed(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        current = self._repository.get(session.session_id)
        if current is not None and current.model_dump(mode="json") == session.model_dump(mode="json"):
            return current
        saved = self._repository.save(session)
        self._publish_session_updated(saved, hub)
        return saved

    def _collect_verification_commands(self, session: OrchestratorSession) -> list[str]:
        if session.plan is None:
            return []
        commands: list[str] = []
        seen: set[str] = set()
        for task in session.plan.tasks:
            for command in task.acceptance_commands:
                normalized = command.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                commands.append(normalized)
        return commands

    def _normalize_changed_files(self, project_path: str, result: OrchestratorDelegateResult) -> list[str]:
        project_root = Path(project_path).resolve()
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_path in result.changed_files:
            candidate = Path(raw_path)
            if candidate.is_absolute():
                try:
                    rel = candidate.resolve().relative_to(project_root)
                    value = rel.as_posix()
                except ValueError:
                    value = candidate.as_posix()
            else:
                value = candidate.as_posix().lstrip("./")
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    def _validate_changed_files(self, task: OrchestratorTask, changed_files: list[str]) -> str | None:
        if not changed_files:
            return None

        forbidden_paths = {".git", ".data", "node_modules", "dist", "build", "target"}
        scope_paths = [item.strip().strip("/") for item in task.scope_paths if item.strip()]
        if not scope_paths or "." in scope_paths:
            scope_paths = ["."]

        for changed_file in changed_files:
            normalized = changed_file.strip().strip("/")
            if not normalized:
                continue
            if any(normalized == forbidden or normalized.startswith(f"{forbidden}/") for forbidden in forbidden_paths):
                return f"delegate changed forbidden path: {changed_file}"
            if scope_paths == ["."]:
                continue
            if not any(normalized == scope or normalized.startswith(f"{scope}/") for scope in scope_paths):
                return f"delegate changed file outside approved scope: {changed_file}"
        return None

    def _validate_expected_file_change_evidence(self, task: OrchestratorTask, changed_files: list[str]) -> str | None:
        if not self._requires_file_change_evidence(task):
            return None
        if changed_files:
            return None
        return "delegate reported success but no changed files for a file-creation task"

    def _requires_file_change_evidence(self, task: OrchestratorTask) -> bool:
        if task.kind != OrchestratorTaskKind.IMPLEMENT:
            return False

        artifacts = task.artifacts or {}
        text_parts = [task.title]
        for value in [
            task.assignment_requested_objective,
            task.assignment_directive,
            artifacts.get("requested_objective"),
            artifacts.get("directive"),
        ]:
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
        merged_text = " ".join(text_parts)
        if not merged_text:
            return False

        has_create_intent = bool(
            re.search(
                r"(创建|新建|新增|生成|写入|产出|create|add|write|generate|scaffold|bootstrap)",
                merged_text,
                flags=re.IGNORECASE,
            )
        )
        if not has_create_intent:
            return False
        return bool(
            re.search(
                r"(文件|file|markdown|readme|文档|\.[a-z0-9]{1,8}\b)",
                merged_text,
                flags=re.IGNORECASE,
            )
        )

    def _complete_delegate_record(
        self,
        session: OrchestratorSession,
        task_id: str,
        delegate_run_id: str,
        succeeded: bool,
    ) -> list[OrchestratorDelegateRun]:
        completed: list[OrchestratorDelegateRun] = []
        for item in session.delegates:
            if item.task_id == task_id and item.delegate_run_id == delegate_run_id:
                completed.append(
                    item.model_copy(
                        update={
                            "status": "succeeded" if succeeded else "failed",
                            "completed_at": self._now(),
                        }
                    )
                )
            else:
                completed.append(item)
        return completed

    def _all_tasks_succeeded(self, session: OrchestratorSession) -> bool:
        return session.plan is not None and all(task.status == OrchestratorTaskStatus.SUCCEEDED for task in session.plan.tasks)

    def _get_session(self, session_id: str) -> OrchestratorSession:
        session = self._repository.get(session_id)
        if session is None:
            raise ValueError("orchestrator session not found")
        recovered = self._recover_stuck_verifying_session(session)
        recovered = self._recover_stalled_running_tasks(recovered)
        return self._normalize_session_task_runtime_fields(recovered)

    def _recover_stuck_verifying_session(self, session: OrchestratorSession) -> OrchestratorSession:
        if session.status != OrchestratorSessionStatus.VERIFYING:
            return session
        if session.verification is not None:
            return session
        if not self._all_tasks_succeeded(session):
            return session

        now = self._now()
        if now - session.updated_at < self._stuck_verifying_timeout:
            return session

        summary = "统一验收状态疑似中断（超过 15 分钟无更新），已自动标记为失败，请恢复推进重跑验收。"
        recovered = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.FAILED,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.FAILED,
                    priority_score=self._priority_score(session),
                    waiting_reason=summary,
                    failure_category=OrchestratorFailureCategory.VERIFICATION_FAILURE,
                ),
                "summary": summary,
                "updated_at": now,
            }
        )
        saved = self._repository.save(recovered)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="主控统一验收疑似中断，已自动标记为失败，等待恢复。")
        if self._conversation_service is not None:
            self._conversation_service.append_system_event(
                saved,
                summary=summary,
                blocks=[self._conversation_service.build_session_status_block(saved)],
            )
        return saved

    def _recover_stalled_running_tasks(
        self,
        session: OrchestratorSession,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        if session.plan is None:
            return session
        if session.status in self._terminal_statuses():
            return session

        now = self._now()
        changed = False
        followup_events: list[tuple[OrchestratorTask, str]] = []
        updated_tasks: list[OrchestratorTask] = []

        for task in session.plan.tasks:
            if task.status != OrchestratorTaskStatus.RUNNING:
                updated_tasks.append(task)
                continue

            assigned_at = task.assigned_at
            if assigned_at is None:
                assigned_at = self._parse_iso_datetime(task.artifacts.get("assigned_at"))
            if assigned_at is None:
                assigned_at = session.updated_at
            if assigned_at.tzinfo is None:
                assigned_at = assigned_at.replace(tzinfo=timezone.utc)

            elapsed = now - assigned_at
            if elapsed < self._delegate_soft_ping_timeout:
                updated_tasks.append(task)
                continue

            last_followup_at = task.last_stall_followup_at
            if last_followup_at is None:
                last_followup_at = self._parse_iso_datetime(task.artifacts.get("last_stall_followup_at"))
            if (
                last_followup_at is not None
                and now - last_followup_at < self._delegate_stall_followup_interval
            ):
                updated_tasks.append(task)
                continue

            _, engineer_label = self._resolve_engineer_identity(task)
            level = "hard_intervention" if elapsed >= self._delegate_no_receipt_timeout else "soft_ping"
            followup = self._build_stall_followup(
                task,
                engineer_label=engineer_label,
                elapsed=elapsed,
                level=level,
            )
            stalled_at = task.artifacts.get("stalled_at")
            if level == "hard_intervention" and not isinstance(stalled_at, str):
                stalled_at = now.isoformat()
            updated_task = task.model_copy(
                update={
                    "result_summary": followup.manager_summary,
                    "stall_level": level,
                    "stall_followup": followup,
                    "last_stall_followup_at": now,
                    "last_intervened_at": now,
                    "intervention_suggestions": [item for item in followup.suggestions if item.strip()],
                    "artifacts": {
                        **task.artifacts,
                        "stalled": bool(task.artifacts.get("stalled")) or level == "hard_intervention",
                        "stall_level": level,
                        "stalled_at": stalled_at,
                        "last_stall_followup_at": now.isoformat(),
                        "last_followup_directive": None,
                        "stall_followup": followup.model_dump(mode="json"),
                    },
                }
            )
            updated_tasks.append(updated_task)
            phase = "主控主动介入排障" if level == "hard_intervention" else "主控追问卡点"
            followup_events.append((updated_task, phase))
            changed = True

        if not changed:
            return session

        preferred_summary = next(
            (
                task.result_summary
                for task, phase in followup_events
                if phase == "主控主动介入排障" and task.result_summary
            ),
            None,
        )
        summary = (
            preferred_summary
            or followup_events[0][0].result_summary
            or session.summary
            or "主控检测到执行卡点，已主动介入。"
        )
        updated = session.model_copy(
            update={
                "plan": session.plan.model_copy(update={"tasks": updated_tasks}),
                "summary": summary,
                "coordination": self._copy_coordination(
                    session,
                    priority_score=self._priority_score(session),
                ).model_copy(
                    update={
                        "mode": OrchestratorCoordinationMode.RUNNING,
                        "waiting_reason": summary,
                    }
                ),
                "updated_at": now,
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=summary)
        if self._conversation_service is not None:
            for followup_task, phase in followup_events:
                self._conversation_service.append_task_update(
                    saved,
                    followup_task,
                    phase=phase,
                    hub=hub,
                )
        for followup_task, _ in followup_events:
            self._publish_task_updated(saved, followup_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _build_stall_followup(
        self,
        task: OrchestratorTask,
        *,
        engineer_label: str,
        elapsed: timedelta,
        level: str,
    ) -> OrchestratorTaskStallFollowup:
        elapsed_hours = max(1, int(elapsed.total_seconds() // 3600))
        followup_command = self._build_engineer_followup_command(engineer_label)

        if level == "hard_intervention":
            manager_summary = (
                f"{engineer_label} 执行任务「{task.title}」超过 {elapsed_hours} 小时未回执，"
                "主控已介入排障并下发建议。"
            )
            engineer_prompt = (
                f"{engineer_label}，请先反馈当前卡点（最近命令、错误日志、阻塞文件），"
                "然后按建议顺序尝试最小修复路径。"
            )
        elif level == "manual_followup":
            manager_summary = f"主控已按指令追问 {engineer_label} 的卡点并下发建议。"
            engineer_prompt = (
                f"{engineer_label}，请同步当前阻塞点、尝试过的方案与下一步计划，"
                "优先给出可在 30 分钟内验证的最小行动。"
            )
        else:
            manager_summary = (
                f"{engineer_label} 执行任务「{task.title}」已持续 {elapsed_hours} 小时，"
                "主控先发起进度追问并给出排障建议。"
            )
            engineer_prompt = (
                f"{engineer_label}，请先回执当前进展与卡点；若已阻塞，"
                "按建议执行最小定位与修复路径。"
            )

        suggestions = [
            "先给出最近一次失败命令和错误摘要，明确是环境问题、依赖问题还是实现问题。",
            "把改动范围缩到当前任务 scope，先提交最小可验证改动，再扩展。",
            "先跑一条最小验收命令定位失败边界，再决定是否拆分子任务。",
        ]
        return OrchestratorTaskStallFollowup(
            level=level,
            elapsed_minutes=max(1, int(elapsed.total_seconds() // 60)),
            manager_summary=manager_summary,
            engineer_prompt=engineer_prompt,
            suggestions=suggestions,
            followup_command=followup_command,
        )

    def _parse_iso_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _normalize_session_task_runtime_fields(self, session: OrchestratorSession) -> OrchestratorSession:
        if session.plan is None:
            return session

        changed = False
        normalized_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            normalized = self._normalize_task_runtime_fields(task)
            normalized_tasks.append(normalized)
            if normalized is not task:
                changed = True
        if not changed:
            return session
        return session.model_copy(
            update={
                "plan": session.plan.model_copy(update={"tasks": normalized_tasks}),
            }
        )

    def _normalize_task_runtime_fields(self, task: OrchestratorTask) -> OrchestratorTask:
        artifacts = task.artifacts or {}
        has_update = False

        assignment_source = task.assignment_source.strip() if isinstance(task.assignment_source, str) else None
        if not assignment_source:
            fallback_assignment_source = artifacts.get("source")
            if isinstance(fallback_assignment_source, str) and fallback_assignment_source.strip():
                assignment_source = fallback_assignment_source.strip()
                has_update = True
            else:
                assignment_source = None

        assignment_directive = task.assignment_directive.strip() if isinstance(task.assignment_directive, str) else None
        if not assignment_directive:
            fallback_assignment_directive = artifacts.get("directive")
            if isinstance(fallback_assignment_directive, str) and fallback_assignment_directive.strip():
                assignment_directive = fallback_assignment_directive.strip()
                has_update = True
            else:
                assignment_directive = None

        assignment_requested_objective = (
            task.assignment_requested_objective.strip()
            if isinstance(task.assignment_requested_objective, str)
            else None
        )
        if not assignment_requested_objective:
            fallback_assignment_objective = artifacts.get("requested_objective")
            if isinstance(fallback_assignment_objective, str) and fallback_assignment_objective.strip():
                assignment_requested_objective = fallback_assignment_objective.strip()
                has_update = True
            else:
                assignment_requested_objective = None

        assignment_scope_override = task.assignment_scope_override
        if assignment_scope_override is None:
            fallback_scope_override = artifacts.get("scope_override")
            if isinstance(fallback_scope_override, list):
                parsed_scope_override = [
                    item.strip() for item in fallback_scope_override if isinstance(item, str) and item.strip()
                ]
                assignment_scope_override = parsed_scope_override
                has_update = True

        assignment_resolved_scope_override = task.assignment_resolved_scope_override
        if assignment_resolved_scope_override is None:
            fallback_resolved_scope_override = artifacts.get("resolved_scope_override")
            if isinstance(fallback_resolved_scope_override, list):
                parsed_resolved_scope = [
                    item.strip()
                    for item in fallback_resolved_scope_override
                    if isinstance(item, str) and item.strip()
                ]
                assignment_resolved_scope_override = parsed_resolved_scope
                has_update = True

        assignment_acceptance_override = task.assignment_acceptance_override
        if assignment_acceptance_override is None:
            fallback_acceptance_override = artifacts.get("acceptance_override")
            if isinstance(fallback_acceptance_override, list):
                parsed_acceptance_override = [
                    item.strip()
                    for item in fallback_acceptance_override
                    if isinstance(item, str) and item.strip()
                ]
                assignment_acceptance_override = parsed_acceptance_override
                has_update = True

        assignment_priority_override = task.assignment_priority_override
        if assignment_priority_override is None:
            fallback_priority_override = artifacts.get("priority_override")
            if isinstance(fallback_priority_override, int):
                assignment_priority_override = fallback_priority_override
                has_update = True

        engineer_id = task.engineer_id
        if not isinstance(engineer_id, int) or engineer_id <= 0:
            fallback_engineer_id = artifacts.get("engineer_id")
            if isinstance(fallback_engineer_id, int) and fallback_engineer_id > 0:
                engineer_id = fallback_engineer_id
                has_update = True
            else:
                engineer_id = None

        engineer_label = task.engineer_label.strip() if isinstance(task.engineer_label, str) else None
        if not engineer_label:
            fallback_engineer_label = artifacts.get("engineer_label")
            if isinstance(fallback_engineer_label, str) and fallback_engineer_label.strip():
                engineer_label = fallback_engineer_label.strip()
                has_update = True
            elif engineer_id is not None:
                engineer_label = f"工程师{engineer_id}号(codex)"
                has_update = True
            else:
                engineer_label = None

        assigned_at = task.assigned_at
        if assigned_at is None:
            fallback_assigned_at = self._parse_iso_datetime(artifacts.get("assigned_at"))
            if fallback_assigned_at is not None:
                assigned_at = fallback_assigned_at
                has_update = True

        stall_level = task.stall_level.strip() if isinstance(task.stall_level, str) else None
        if not stall_level:
            fallback_stall_level = artifacts.get("stall_level")
            if isinstance(fallback_stall_level, str) and fallback_stall_level.strip():
                stall_level = fallback_stall_level.strip()
                has_update = True
            else:
                stall_level = None

        stall_followup = task.stall_followup
        if stall_followup is None:
            raw_stall_followup = artifacts.get("stall_followup")
            if isinstance(raw_stall_followup, dict):
                try:
                    stall_followup = OrchestratorTaskStallFollowup.model_validate(raw_stall_followup)
                    has_update = True
                except ValueError:
                    stall_followup = None

        last_stall_followup_at = task.last_stall_followup_at
        if last_stall_followup_at is None:
            fallback_last_followup = self._parse_iso_datetime(artifacts.get("last_stall_followup_at"))
            if fallback_last_followup is not None:
                last_stall_followup_at = fallback_last_followup
                has_update = True

        last_intervened_at = task.last_intervened_at
        if last_intervened_at is None and last_stall_followup_at is not None:
            last_intervened_at = last_stall_followup_at
            has_update = True

        intervention_suggestions = [item for item in task.intervention_suggestions if item.strip()]
        if not intervention_suggestions:
            if stall_followup is not None:
                intervention_suggestions = [item for item in stall_followup.suggestions if item.strip()]
                if intervention_suggestions:
                    has_update = True

        if not has_update:
            return task
        return task.model_copy(
            update={
                "assignment_source": assignment_source,
                "assignment_directive": assignment_directive,
                "assignment_requested_objective": assignment_requested_objective,
                "assignment_scope_override": assignment_scope_override,
                "assignment_resolved_scope_override": assignment_resolved_scope_override,
                "assignment_acceptance_override": assignment_acceptance_override,
                "assignment_priority_override": assignment_priority_override,
                "engineer_id": engineer_id,
                "engineer_label": engineer_label,
                "assigned_at": assigned_at,
                "stall_level": stall_level,
                "stall_followup": stall_followup,
                "last_stall_followup_at": last_stall_followup_at,
                "last_intervened_at": last_intervened_at,
                "intervention_suggestions": intervention_suggestions,
            }
        )

    def _normalize_filter_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _matches_session_filters(
        self,
        session: OrchestratorSession,
        *,
        statuses: list[OrchestratorSessionStatus] | None,
        project: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
        keyword: str | None,
    ) -> bool:
        if statuses:
            allowed = set(statuses)
            if session.status not in allowed:
                return False

        normalized_project = (project or "").strip().lower()
        if normalized_project:
            haystack = " ".join([session.project_name, session.project_path]).lower()
            if normalized_project not in haystack:
                return False

        normalized_from = self._normalize_filter_datetime(from_time)
        normalized_to = self._normalize_filter_datetime(to_time)
        session_updated_at = session.updated_at
        if session_updated_at.tzinfo is None:
            session_updated_at = session_updated_at.replace(tzinfo=timezone.utc)
        else:
            session_updated_at = session_updated_at.astimezone(timezone.utc)

        if normalized_from is not None and session_updated_at < normalized_from:
            return False
        if normalized_to is not None and session_updated_at > normalized_to:
            return False

        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword:
            task_titles = []
            if session.plan is not None:
                task_titles = [task.title for task in session.plan.tasks]
            keyword_haystack = " ".join(
                [
                    session.goal,
                    session.project_name,
                    session.project_path,
                    session.summary or "",
                    *task_titles,
                ]
            ).lower()
            if normalized_keyword not in keyword_haystack:
                return False

        return True

    def _is_task_already_stopped_by_orchestrator(self, task: OrchestratorTask) -> bool:
        if task.status not in {OrchestratorTaskStatus.FAILED, OrchestratorTaskStatus.CANCELLED}:
            return False
        artifacts = task.artifacts or {}
        stopped_flag = artifacts.get("stopped_by_orchestrator")
        if isinstance(stopped_flag, bool) and stopped_flag:
            return True
        delegate_result = artifacts.get("delegate_result")
        if isinstance(delegate_result, dict):
            error = delegate_result.get("error")
            if isinstance(error, str) and "delegate stopped by orchestrator" in error:
                return True
        if isinstance(task.error, str) and "delegate stopped by orchestrator" in task.error:
            return True
        return False

    def _get_task(self, session: OrchestratorSession, task_id: str) -> OrchestratorTask:
        if session.plan is None:
            raise ValueError("session plan is not ready")
        for task in session.plan.tasks:
            if task.task_id == task_id:
                return task
        raise ValueError("orchestrator task not found")

    def _find_task_for_followup_directive(self, session: OrchestratorSession, directive: str) -> OrchestratorTask | None:
        if session.plan is None:
            return None
        normalized = directive.strip()
        if not normalized:
            return None
        for task in session.plan.tasks:
            if task.status != OrchestratorTaskStatus.RUNNING:
                continue
            tagged_directive = task.artifacts.get("last_followup_directive")
            if isinstance(tagged_directive, str) and tagged_directive.strip() == normalized:
                return task
        return None

    def _validate_project_path(self, project_path: str) -> str:
        resolved = str(Path(project_path).expanduser().resolve())
        permissions = get_runtime_config().list_folder_permissions()
        if not permissions:
            raise ValueError("no imported project is available for orchestrator mode")
        for granted_path, access_level in permissions:
            if str(Path(granted_path).expanduser().resolve()) == resolved:
                return resolved
        raise ValueError("project_path is not part of the imported project registry")

    def _is_active_session(self, session_id: str) -> bool:
        current = self._state_store.get().orchestrator_session
        return current is not None and current.session_id == session_id

    def _active_session_id(self) -> str | None:
        current = self._state_store.get().orchestrator_session
        return None if current is None else current.session_id

    def _publish_session_updated(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None:
            hub.publish_orchestrator_session_updated(session.model_dump(mode="json"))

    def _publish_task_updated(
        self,
        session: OrchestratorSession,
        task: OrchestratorTask,
        hub: AppRealtimeHub | None,
    ) -> None:
        if hub is not None:
            hub.publish_orchestrator_task_updated(
                {
                    "session_id": session.session_id,
                    "task": task.model_dump(mode="json"),
                }
            )

    def _publish_plan_pending(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None and session.plan is not None:
            hub.publish_orchestrator_plan_pending_approval(
                {
                    "session_id": session.session_id,
                    "plan": session.plan.model_dump(mode="json"),
                }
            )

    def _publish_verification_completed(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None and session.verification is not None:
            hub.publish_orchestrator_verification_completed(
                {
                    "session_id": session.session_id,
                    "verification": session.verification.model_dump(mode="json"),
                    "status": session.status.value,
                }
            )

    def _terminal_statuses(self) -> set[OrchestratorSessionStatus]:
        return {
            OrchestratorSessionStatus.COMPLETED,
            OrchestratorSessionStatus.FAILED,
            OrchestratorSessionStatus.CANCELLED,
        }

    def _apply_scope_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        paths = self._extract_scope_paths(message)
        if paths is None:
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if any(
            task.status == OrchestratorTaskStatus.RUNNING
            and task.kind in {OrchestratorTaskKind.ANALYZE, OrchestratorTaskKind.IMPLEMENT}
            for task in session.plan.tasks
        ):
            raise ValueError("cannot change scope while analyze/implement delegate is running")

        updated_tasks: list[OrchestratorTask] = []
        changed = False
        for task in session.plan.tasks:
            if task.kind in {OrchestratorTaskKind.ANALYZE, OrchestratorTaskKind.IMPLEMENT} and task.status != OrchestratorTaskStatus.SUCCEEDED:
                next_artifacts = task.artifacts
                if task.kind == OrchestratorTaskKind.IMPLEMENT:
                    next_artifacts = self._reset_secondary_approval_artifacts(task.artifacts)
                next_task = task.model_copy(update={"scope_paths": paths, "artifacts": next_artifacts})
                updated_tasks.append(next_task)
                changed = changed or next_task.scope_paths != task.scope_paths
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if not changed:
            raise ValueError("scope_paths already match the requested directive")

        summary = f"主控边界已更新，后续分析/实现仅允许作用于：{', '.join(paths)}"
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        return session.model_copy(
            update={
                "plan": updated_plan,
                "summary": summary,
                "coordination": self._copy_coordination(session, priority_score=self._priority_score(session)),
                "updated_at": self._now(),
            }
        )

    def _apply_acceptance_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        commands = self._extract_acceptance_commands(message)
        if commands is None:
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status == OrchestratorSessionStatus.VERIFYING or any(
            task.status == OrchestratorTaskStatus.RUNNING
            and task.kind in {OrchestratorTaskKind.VERIFY, OrchestratorTaskKind.SUMMARIZE}
            for task in session.plan.tasks
        ):
            raise ValueError("cannot change acceptance commands while verification is running")

        updated_tasks: list[OrchestratorTask] = []
        changed = False
        for task in session.plan.tasks:
            if task.kind in {OrchestratorTaskKind.IMPLEMENT, OrchestratorTaskKind.VERIFY} and task.status != OrchestratorTaskStatus.SUCCEEDED:
                next_artifacts = task.artifacts
                if task.kind == OrchestratorTaskKind.IMPLEMENT:
                    next_artifacts = self._reset_secondary_approval_artifacts(task.artifacts)
                next_task = task.model_copy(update={"acceptance_commands": commands, "artifacts": next_artifacts})
                updated_tasks.append(next_task)
                changed = changed or next_task.acceptance_commands != task.acceptance_commands
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if not changed:
            raise ValueError("acceptance commands already match the requested directive")

        summary = f"计划内验收命令已更新为：{' | '.join(commands)}"
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        return session.model_copy(
            update={
                "plan": updated_plan,
                "verification": None,
                "summary": summary,
                "coordination": self._copy_coordination(session, priority_score=self._priority_score(session)),
                "updated_at": self._now(),
            }
        )

    def _apply_secondary_approval_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        normalized = message.strip()
        if not re.search(r"(高风险|二次审批|risk)", normalized, flags=re.IGNORECASE):
            return None
        if not re.search(r"(批准|确认|允许|继续)", normalized):
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")

        target_task: OrchestratorTask | None = None
        for task in session.plan.tasks:
            if task.kind != OrchestratorTaskKind.IMPLEMENT:
                continue
            if task.status == OrchestratorTaskStatus.SUCCEEDED:
                continue
            risk_reason = self._resolve_high_risk_reason(task)
            if risk_reason is None:
                continue
            if task.artifacts.get("secondary_approval_granted") is True:
                continue
            target_task = task
            break

        if target_task is None:
            raise ValueError("no high-risk task is waiting for secondary approval")

        updated_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            if task.task_id == target_task.task_id:
                updated_tasks.append(
                    task.model_copy(
                        update={
                            "status": OrchestratorTaskStatus.PENDING,
                            "artifacts": {
                                **task.artifacts,
                                "secondary_approval_required": True,
                                "secondary_approval_granted": True,
                                "secondary_approved_at": self._now().isoformat(),
                            },
                        }
                    )
                )
            else:
                updated_tasks.append(task.model_copy(deep=True))

        summary = f"已批准高风险任务：{target_task.title}"
        coordination = self._copy_coordination(session, priority_score=self._priority_score(session)).model_copy(
            update={
                "mode": OrchestratorCoordinationMode.READY,
                "waiting_reason": "高风险任务已批准，等待调度派发。",
                "queue_position": None,
                "preempted_by_session_id": None,
                "failure_category": None,
            }
        )
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        return session.model_copy(
            update={
                "plan": updated_plan,
                "status": OrchestratorSessionStatus.DISPATCHING,
                "summary": summary,
                "coordination": coordination,
                "updated_at": self._now(),
            }
        )

    def _apply_priority_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        normalized = message.strip()
        priority_bias: int | None = None
        summary: str | None = None

        if re.search(r"(提到最高|最高优先级|优先级最高|加急)", normalized):
            priority_bias = 80
            summary = "当前主控会话已提到最高优先级。"
        elif re.search(r"(降低优先级|低优先级|延后处理)", normalized):
            priority_bias = -40
            summary = "当前主控会话已降为低优先级。"
        elif re.search(r"(恢复普通优先级|普通优先级|默认优先级)", normalized):
            priority_bias = 0
            summary = "当前主控会话已恢复普通优先级。"

        if priority_bias is None or summary is None:
            return None
        if session.priority_bias == priority_bias:
            raise ValueError("session priority already matches the requested directive")

        updated = session.model_copy(
            update={
                "priority_bias": priority_bias,
                "summary": summary,
                "updated_at": self._now(),
            }
        )
        return updated.model_copy(
            update={
                "coordination": self._copy_coordination(updated, priority_score=self._priority_score(updated)),
            }
        )

    def _apply_engineer_followup_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        normalized = message.strip()
        if not re.search(r"(追问|询问|问一下|问|催|跟进)", normalized):
            return None
        if not re.search(r"(工程师|卡点|阻塞|进度|回执|卡住)", normalized):
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")

        running_tasks = [task for task in session.plan.tasks if task.status == OrchestratorTaskStatus.RUNNING]
        if not running_tasks:
            raise ValueError("no running task available for engineer follow-up")

        engineer_id: int | None = None
        engineer_match = re.search(r"工程师\s*(\d+)\s*号", normalized)
        if engineer_match is not None:
            try:
                engineer_id = int(engineer_match.group(1))
            except ValueError:
                engineer_id = None

        target_task: OrchestratorTask | None = None
        if engineer_id is not None and engineer_id > 0:
            for task in running_tasks:
                task_engineer_id, _ = self._resolve_engineer_identity(task)
                if task_engineer_id == engineer_id:
                    target_task = task
                    break
            if target_task is None:
                raise ValueError(f"工程师{engineer_id}号当前没有运行中的任务")
        else:
            if len(running_tasks) > 1:
                raise ValueError("存在多个运行中任务，请指定工程师编号")
            target_task = running_tasks[0]

        _, engineer_label = self._resolve_engineer_identity(target_task)
        now = self._now()
        assigned_at = target_task.assigned_at
        if assigned_at is None:
            assigned_at = self._parse_iso_datetime(target_task.artifacts.get("assigned_at"))
        if assigned_at is None:
            assigned_at = session.updated_at
        if assigned_at.tzinfo is None:
            assigned_at = assigned_at.replace(tzinfo=timezone.utc)
        elapsed = max(timedelta(minutes=1), now - assigned_at)

        followup = self._build_stall_followup(
            target_task,
            engineer_label=engineer_label,
            elapsed=elapsed,
            level="manual_followup",
        )
        summary = followup.manager_summary or "主控已追问执行卡点。"

        updated_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            if task.task_id == target_task.task_id:
                updated_tasks.append(
                    task.model_copy(
                        update={
                            "result_summary": summary,
                            "stall_level": "manual_followup",
                            "stall_followup": followup,
                            "last_stall_followup_at": now,
                            "last_intervened_at": now,
                            "intervention_suggestions": [item for item in followup.suggestions if item.strip()],
                            "artifacts": {
                                **task.artifacts,
                                "stalled": bool(task.artifacts.get("stalled")),
                                "stall_level": "manual_followup",
                                "last_stall_followup_at": now.isoformat(),
                                "last_followup_directive": normalized,
                                "stall_followup": followup.model_dump(mode="json"),
                            },
                        }
                    )
                )
            else:
                updated_tasks.append(task.model_copy(deep=True))

        coordination = self._copy_coordination(session, priority_score=self._priority_score(session)).model_copy(
            update={
                "mode": OrchestratorCoordinationMode.RUNNING,
                "waiting_reason": summary,
            }
        )
        return session.model_copy(
            update={
                "plan": session.plan.model_copy(update={"tasks": updated_tasks}),
                "status": OrchestratorSessionStatus.RUNNING,
                "summary": summary,
                "coordination": coordination,
                "updated_at": now,
            }
        )

    def _apply_task_assignment_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        assignment_payload = self._extract_task_assignment_payload(message)
        if assignment_payload is None:
            return None
        objective, scope_override, acceptance_override, priority_override = assignment_payload
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status == OrchestratorSessionStatus.VERIFYING or any(
            task.status == OrchestratorTaskStatus.RUNNING
            and task.kind in {OrchestratorTaskKind.VERIFY, OrchestratorTaskKind.SUMMARIZE}
            for task in session.plan.tasks
        ):
            raise ValueError("cannot add task while verification is running")

        next_priority_bias = session.priority_bias if priority_override is None else priority_override
        working_session = (
            session
            if next_priority_bias == session.priority_bias
            else session.model_copy(update={"priority_bias": next_priority_bias})
        )

        task_id = self._next_chat_implement_task_id(session)
        resolved_scope_override = scope_override or self._infer_scope_paths_from_chat_objective(objective)
        scope_paths = resolved_scope_override or self._default_scope_paths_for_chat_task(session)
        acceptance_commands = acceptance_override or self._default_acceptance_commands_for_chat_task(session)
        depends_on = [task.task_id for task in session.plan.tasks if task.kind == OrchestratorTaskKind.ANALYZE]
        chat_task = OrchestratorTask(
            task_id=task_id,
            title=f"聊天指派：{objective}",
            kind=OrchestratorTaskKind.IMPLEMENT,
            scope_paths=scope_paths,
            acceptance_commands=acceptance_commands,
            depends_on=depends_on,
            assignment_source="chat_assignment",
            assignment_directive=message,
            assignment_requested_objective=objective,
            assignment_scope_override=scope_override,
            assignment_resolved_scope_override=resolved_scope_override,
            assignment_acceptance_override=acceptance_override,
            assignment_priority_override=priority_override,
            artifacts={
                "source": "chat_assignment",
                "directive": message,
                "requested_objective": objective,
                "scope_override": scope_override,
                "resolved_scope_override": resolved_scope_override,
                "acceptance_override": acceptance_override,
                "priority_override": priority_override,
            },
        )

        tasks_with_inserted_chat_task: list[OrchestratorTask] = []
        inserted = False
        for task in session.plan.tasks:
            if not inserted and task.kind == OrchestratorTaskKind.VERIFY:
                tasks_with_inserted_chat_task.append(chat_task)
                inserted = True
            tasks_with_inserted_chat_task.append(task.model_copy(deep=True))
        if not inserted:
            tasks_with_inserted_chat_task.append(chat_task)

        implement_ids = [
            task.task_id
            for task in tasks_with_inserted_chat_task
            if task.kind == OrchestratorTaskKind.IMPLEMENT
        ]
        updated_tasks: list[OrchestratorTask] = []
        for task in tasks_with_inserted_chat_task:
            if task.kind == OrchestratorTaskKind.VERIFY:
                verify_task = task.model_copy(update={"depends_on": list(dict.fromkeys(implement_ids))})
                if verify_task.status != OrchestratorTaskStatus.PENDING:
                    verify_task = self._reset_task_for_resume(verify_task).model_copy(
                        update={"depends_on": list(dict.fromkeys(implement_ids))}
                    )
                updated_tasks.append(verify_task)
                continue
            if task.kind == OrchestratorTaskKind.SUMMARIZE:
                summarize_task = (
                    task
                    if task.status == OrchestratorTaskStatus.PENDING
                    else self._reset_task_for_resume(task)
                )
                updated_tasks.append(summarize_task)
                continue
            updated_tasks.append(task)

        summary_parts = [f"已新增聊天任务（ID: {task_id}），准备交给 Codex：{objective}"]
        if resolved_scope_override is not None:
            summary_parts.append(f"scope={', '.join(scope_paths)}")
        if acceptance_override is not None:
            summary_parts.append(f"验收={ ' | '.join(acceptance_commands)}")
        if priority_override is not None:
            summary_parts.append(f"优先级={self._priority_bias_to_label(next_priority_bias)}")
        summary = "；".join(summary_parts)
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})

        base_coordination = self._copy_coordination(
            working_session,
            priority_score=self._priority_score(working_session),
        )
        if session.status == OrchestratorSessionStatus.PENDING_PLAN_APPROVAL:
            coordination = base_coordination.model_copy(
                update={
                    "mode": OrchestratorCoordinationMode.IDLE,
                    "waiting_reason": "计划已追加聊天任务，等待计划审批。",
                    "queue_position": None,
                    "dispatch_slot": None,
                    "preempted_by_session_id": None,
                    "failure_category": None,
                }
            )
            return session.model_copy(
                update={
                    "plan": updated_plan,
                    "verification": None,
                    "summary": summary,
                    "priority_bias": next_priority_bias,
                    "coordination": coordination,
                    "updated_at": self._now(),
                }
            )

        coordination = base_coordination.model_copy(
            update={
                "mode": OrchestratorCoordinationMode.READY,
                "waiting_reason": "已新增聊天任务，等待调度器派发。",
                "queue_position": None,
                "dispatch_slot": None,
                "preempted_by_session_id": None,
                "failure_category": None,
            }
        )
        return session.model_copy(
            update={
                "plan": updated_plan,
                "status": OrchestratorSessionStatus.DISPATCHING,
                "verification": None,
                "summary": summary,
                "priority_bias": next_priority_bias,
                "coordination": coordination,
                "updated_at": self._now(),
            }
        )

    def _reset_secondary_approval_artifacts(self, artifacts: dict[str, object]) -> dict[str, object]:
        cleaned = dict(artifacts)
        for key in [
            "secondary_approval_required",
            "secondary_approval_reason",
            "secondary_approval_granted",
            "secondary_approved_at",
        ]:
            cleaned.pop(key, None)
        return cleaned

    def _copy_coordination(
        self,
        session: OrchestratorSession,
        *,
        priority_score: int,
    ) -> OrchestratorSessionCoordination:
        if session.coordination is None:
            return OrchestratorSessionCoordination(
                mode=OrchestratorCoordinationMode.IDLE,
                priority_score=priority_score,
                waiting_reason=session.summary,
                failure_category=None,
            )
        return session.coordination.model_copy(update={"priority_score": priority_score})

    def _extract_scope_paths(self, message: str) -> list[str] | None:
        patterns = [
            r"(?:scope|范围|改动范围).{0,12}(?:限制在|限定到|改成|设为)\s*(.+)$",
            r"(?:只允许改|只改|限定在|限定到)\s*(.+)$",
        ]
        raw_value: str | None = None
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                break
        if raw_value is None:
            return None
        return self._extract_scope_paths_from_value(raw_value)

    def _extract_scope_paths_from_value(self, raw_value: str) -> list[str] | None:
        parts = re.split(r"[，,、\n]|(?:\s+和\s+)|(?:\s+and\s+)", raw_value)
        normalized: list[str] = []
        for part in parts:
            item = part.strip().strip("\"'`")
            if not item:
                continue
            if item in {"当前项目", "项目根", "根目录"}:
                item = "."
            item = item.replace("\\", "/").lstrip("./").rstrip("/")
            normalized.append(item or ".")
        deduped = list(dict.fromkeys(normalized))
        return deduped or None

    def _infer_scope_paths_from_chat_objective(self, objective: str) -> list[str] | None:
        normalized = re.sub(r"\s+", " ", objective).strip()
        if not normalized:
            return None
        if self._looks_like_project_root_scope_request(normalized):
            return ["."]
        return None

    def _looks_like_project_root_scope_request(self, text: str) -> bool:
        root_patterns = [
            r"当前目录",
            r"当前工作目录",
            r"本目录",
            r"项目根目录",
            r"仓库根目录",
            r"根目录",
            r"根路径",
            r"\bproject\s+root\b",
            r"\brepository\s+root\b",
            r"\brepo\s+root\b",
            r"\bworkspace\s+root\b",
            r"\bcurrent\s+directory\b",
            r"\bworking\s+directory\b",
            r"\bcwd\b",
        ]
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in root_patterns)

    def _extract_acceptance_commands(self, message: str) -> list[str] | None:
        patterns = [
            r"(?:验收命令|测试命令|验证命令).{0,8}(?:改成|换成|设为|只跑|变更为)\s*(.+)$",
        ]
        raw_value: str | None = None
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                break
        if raw_value is None:
            return None
        return self._extract_acceptance_commands_from_value(raw_value, include_pipe_separator=False)

    def _extract_acceptance_commands_from_value(
        self,
        raw_value: str,
        *,
        include_pipe_separator: bool,
    ) -> list[str] | None:
        separators = r"[；;\n]+"
        if include_pipe_separator:
            separators = r"(?:[；;\n]+|\s*\|\s*)"
        commands = [
            item.strip()
            for item in re.split(separators, raw_value)
            if item.strip()
        ]
        return list(dict.fromkeys(commands)) or None

    def _extract_task_assignment_payload(
        self,
        message: str,
    ) -> tuple[str, list[str] | None, list[str] | None, int | None] | None:
        patterns = [
            r"^(?:请\s*)?(?:给\s*)?(?:codex|主控|你|小晏)?\s*(?:派|指派|安排|新增|添加|创建)(?:一个|个)?(?:新)?任务(?:给(?:codex|主控|你|小晏))?[:：\s]+(.+)$",
            r"^(?:任务|task)\s*[:：]\s*(.+)$",
            r"^(?:请\s*)?(?:把|将)?(?:这个|这项)?任务(?:交给|派给)\s*(?:codex|主控|你|小晏)[:：\s]+(.+)$",
        ]
        raw_payload: str | None = None
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                raw_payload = match.group(1)
                break
        if raw_payload is None:
            return None

        metadata_key_pattern = r"(?:scope|范围|验收|测试|验证|acceptance|priority|优先级)"
        metadata_pattern = re.compile(
            rf"(?:^|[；;\n])\s*(?P<key>{metadata_key_pattern})\s*[:：=]\s*(?P<value>.*?)(?=(?:[；;\n]\s*(?:{metadata_key_pattern})\s*[:：=])|$)",
            flags=re.IGNORECASE,
        )
        scope_override: list[str] | None = None
        acceptance_override: list[str] | None = None
        priority_override: int | None = None
        spans: list[tuple[int, int]] = []

        for match in metadata_pattern.finditer(raw_payload):
            spans.append(match.span())
            key = (match.group("key") or "").strip().lower()
            value = (match.group("value") or "").strip()
            if not value:
                continue

            if key in {"scope", "范围"}:
                parsed_scope = self._extract_scope_paths_from_value(value)
                if parsed_scope is None:
                    raise ValueError("task assignment scope is empty")
                scope_override = parsed_scope
                continue
            if key in {"验收", "测试", "验证", "acceptance"}:
                parsed_commands = self._extract_acceptance_commands_from_value(value, include_pipe_separator=True)
                if parsed_commands is None:
                    raise ValueError("task assignment acceptance commands are empty")
                acceptance_override = parsed_commands
                continue
            if key in {"priority", "优先级"}:
                priority_override = self._extract_priority_bias_from_value(value)

        objective_source = raw_payload
        for start, end in reversed(spans):
            objective_source = f"{objective_source[:start]} {objective_source[end:]}"

        normalized = re.sub(r"\s+", " ", objective_source).strip().strip("\"'`“”")
        normalized = normalized.strip("。；;，,")
        if len(normalized) < 2:
            raise ValueError("task objective is too short")
        if len(normalized) > 120:
            normalized = f"{normalized[:117]}..."
        return normalized, scope_override, acceptance_override, priority_override

    def _extract_priority_bias_from_value(self, raw_value: str) -> int:
        normalized = raw_value.strip().lower()
        if normalized in {"最高", "高", "普通", "低"}:
            return {"最高": 80, "高": 40, "普通": 0, "低": -40}[normalized]
        if re.search(r"(最高|high(est)?|urgent|紧急|加急|p0)", normalized):
            return 80
        if re.search(r"(高优先级|high|p1|较高)", normalized):
            return 40
        if re.search(r"(普通|默认|normal|default|中优先级|p2)", normalized):
            return 0
        if re.search(r"(低优先级|low|延后|p3|较低|降低)", normalized):
            return -40
        raise ValueError("unsupported task assignment priority")

    def _priority_bias_to_label(self, priority_bias: int) -> str:
        if priority_bias >= 80:
            return "最高"
        if priority_bias >= 40:
            return "高"
        if priority_bias <= -40:
            return "低"
        return "普通"

    def _default_scope_paths_for_chat_task(self, session: OrchestratorSession) -> list[str]:
        if session.plan is None:
            return ["."]

        for task in session.plan.tasks:
            if task.kind == OrchestratorTaskKind.IMPLEMENT and task.scope_paths:
                return list(dict.fromkeys(task.scope_paths))
        for task in session.plan.tasks:
            if task.kind == OrchestratorTaskKind.ANALYZE and task.scope_paths:
                return list(dict.fromkeys(task.scope_paths))
        return ["."]

    def _default_acceptance_commands_for_chat_task(self, session: OrchestratorSession) -> list[str]:
        if session.plan is None:
            return ["git status --short"]

        for task in session.plan.tasks:
            if task.kind == OrchestratorTaskKind.IMPLEMENT and task.acceptance_commands:
                return list(dict.fromkeys(task.acceptance_commands))
        for task in session.plan.tasks:
            if task.kind == OrchestratorTaskKind.VERIFY and task.acceptance_commands:
                return list(dict.fromkeys(task.acceptance_commands))
        return ["git status --short"]

    def _next_chat_implement_task_id(self, session: OrchestratorSession) -> str:
        existing_ids = set()
        if session.plan is not None:
            existing_ids = {task.task_id for task in session.plan.tasks}

        index = 1
        while True:
            candidate = f"chat-implement-{index}"
            if candidate not in existing_ids:
                return candidate
            index += 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
